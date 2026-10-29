"""Face detection, anonymous tracking and per-frame behavioral cues from video."""
import time

import cv2
import numpy as np

_FRONTAL = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
_PROFILE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")


def _iou(a, b):
    ax, ay, aw, ah = a[:4]
    bx, by, bw, bh = b[:4]
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    return inter / float(aw * ah + bw * bh - inter) if inter else 0.0


def detect_faces(gray):
    """Return [(x, y, w, h, facing)]. facing is True for frontal faces and False for profiles."""
    side = max(24, gray.shape[1] // 40)
    kw = dict(scaleFactor=1.1, minNeighbors=5, minSize=(side, side))
    faces = [(*map(int, f), True) for f in _FRONTAL.detectMultiScale(gray, **kw)]
    width = gray.shape[1]
    profiles = list(_PROFILE.detectMultiScale(gray, **kw))
    # the profile cascade only finds one side, so also run it on the mirrored frame
    profiles += [(width - x - w, y, w, h) for x, y, w, h in _PROFILE.detectMultiScale(cv2.flip(gray, 1), **kw)]
    for p in profiles:
        if all(_iou(p, f) < 0.3 for f in faces):
            faces.append((*map(int, p), False))
    return faces


class CentroidTracker:
    """Assigns anonymous, persistent IDs to face boxes by nearest-centroid matching."""

    def __init__(self, max_missed):
        self.max_missed = max_missed
        self.next_id = 1
        self.tracks = {}  # id -> {"box": (x, y, w, h), "missed": int}

    def update(self, boxes):
        """Return {box_index: track_id}. Tracks unseen for more than max_missed updates are dropped."""
        pairs = []
        for tid, tr in self.tracks.items():
            tx, ty, tw, th = tr["box"]
            for i, (x, y, w, h, *_) in enumerate(boxes):
                d = np.hypot((x + w / 2) - (tx + tw / 2), (y + h / 2) - (ty + th / 2))
                if d < max(tw, th):
                    pairs.append((d, tid, i))
        assigned, used = {}, set()
        for _, tid, i in sorted(pairs):
            if tid not in used and i not in assigned:
                assigned[i] = tid
                used.add(tid)
        for i, tid in assigned.items():
            self.tracks[tid] = {"box": tuple(boxes[i][:4]), "missed": 0}
        for tid in set(self.tracks) - used:
            self.tracks[tid]["missed"] += 1
            if self.tracks[tid]["missed"] > self.max_missed:
                del self.tracks[tid]
        for i, box in enumerate(boxes):
            if i not in assigned:
                assigned[i] = self.next_id
                self.tracks[self.next_id] = {"box": tuple(box[:4]), "missed": 0}
                self.next_id += 1
        return assigned


def _region_motion(diff, x, y, w, h):
    """Mean absolute frame difference (0 to 1) over the face and upper body region."""
    if diff is None:
        return 0.0
    rows, cols = diff.shape
    region = diff[max(0, y):min(rows, y + 3 * h), max(0, x - w // 2):min(cols, x + w + w // 2)]
    return round(float(region.mean()) / 255, 4) if region.size else 0.0


def analyze_video(source, sample_fps=5.0, max_seconds=None, lost_after=10.0, progress=None):
    """Sample frames from a video file path or webcam index and return (observations, duration_seconds).

    Each observation is a dict with t, track_id, detected, facing and motion. detected=False means the
    person's track is still alive but no face was found in that frame (head down or turned away).
    """
    live = isinstance(source, int)
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video source: {source}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, round(fps / sample_fps))
    tracker = CentroidTracker(max_missed=int(lost_after * fps / step))
    observations, prev, idx, t, start = [], None, 0, 0.0, time.monotonic()
    try:
        while cap.grab():
            idx += 1
            if (idx - 1) % step:
                continue
            ok, frame = cap.retrieve()
            if not ok:
                break
            t = time.monotonic() - start if live else (idx - 1) / fps
            if max_seconds and t > max_seconds:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            diff = cv2.absdiff(gray, prev) if prev is not None else None
            prev = gray
            faces = detect_faces(cv2.equalizeHist(gray))
            seen = {tid: faces[i] for i, tid in tracker.update(faces).items()}
            for tid, tr in tracker.tracks.items():
                face = seen.get(tid)
                observations.append({
                    "t": round(t, 2),
                    "track_id": tid,
                    "detected": face is not None,
                    "facing": bool(face and face[4]),
                    "motion": _region_motion(diff, *tr["box"]),
                })
            if progress and total:
                progress(min(1.0, idx / total))
    finally:
        cap.release()
    duration = total / fps if total and not live and not max_seconds else t
    return observations, duration
