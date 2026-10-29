import cv2
import numpy as np

from engagement_agent import analyze, save_report
from engagement_agent.advisor import suggest
from engagement_agent.analytics import build_report
from engagement_agent.audio import voice_activity
from engagement_agent.vision import CentroidTracker


def test_tracker_keeps_identity_and_drops_lost_tracks():
    tr = CentroidTracker(max_missed=2)
    first = tr.update([(100, 100, 50, 50, True)])
    moved = tr.update([(110, 105, 50, 50, True), (400, 100, 50, 50, True)])
    assert moved[0] == first[0]
    assert moved[1] != first[0]
    for _ in range(3):
        tr.update([])
    assert tr.tracks == {}


def _obs(track_id, seconds, facing, motion=0.05, fps=5, start=0.0):
    return [{"t": start + i / fps, "track_id": track_id, "detected": True, "facing": facing(start + i / fps),
             "motion": motion} for i in range(int(seconds * fps))]


def test_sustained_presence_filters_brief_appearances():
    obs = _obs(1, 120, lambda t: True) + _obs(2, 3, lambda t: True, start=50)
    report = build_report(obs, duration=120, interval=60)
    assert report["session"]["participants"] == 1
    p = report["participants"][0]
    assert p["id"] == "P01" and p["attention_pct"] == 100.0 and p["engagement"] == 100.0
    assert [r["headcount"] for r in report["timeline"]] == [1, 1]


def test_voice_activity_detects_speech_segment():
    sr = 16000
    samples = np.zeros(sr * 4, dtype=np.float32)
    samples[sr:2 * sr] = 0.3 * np.sin(np.linspace(0, 2000 * np.pi, sr))
    times, _, active = voice_activity(samples, sr, window=0.5)
    assert active.tolist() == [False, False, True, True, False, False, False, False]
    assert times[2] == 1.0


def test_advisor_flags_dip_and_decline():
    # attentive for the first 4 minutes, looking away for the last 2
    obs = _obs(1, 360, lambda t: t < 240) + _obs(2, 360, lambda t: t < 240)
    report = build_report(obs, duration=360, interval=60)
    titles = [t["title"] for t in suggest(report)]
    assert any(t.startswith("Attention dip 04:00") for t in titles)
    assert "Engagement declined over the session" in titles


def test_pipeline_runs_on_video_without_people(tmp_path):
    path = str(tmp_path / "blank.avi")
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 10, (160, 120))
    for _ in range(30):
        writer.write(np.full((120, 160, 3), 128, np.uint8))
    writer.release()
    report = analyze(path, interval=1)
    assert report["session"]["participants"] == 0
    assert report["suggestions"][0]["title"] == "No participants detected"
    out = save_report(report, tmp_path / "out")
    assert (out / "report.json").exists() and (out / "attendance.csv").exists()
