"""Fuses vision and audio signals into attendance, per participant and per interval engagement analytics."""
import numpy as np
import pandas as pd

COLUMNS = ["t", "track_id", "detected", "facing", "motion"]


def fmt_time(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def score(attention, activity, speech=None):
    """Engagement on a 0 to 100 scale. Attention (facing forward) carries the most weight."""
    if speech is None:
        return round(100 * (0.75 * attention + 0.25 * activity), 1)
    return round(100 * (0.6 * attention + 0.2 * activity + 0.2 * speech), 1)


def _longest_run(flags):
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best


def build_report(observations, duration, audio=None, sample_fps=5.0, interval=60, min_presence=10.0,
                 still_threshold=0.015):
    """Build the session report. `audio` is the (times, rms, active) tuple from voice_activity or None."""
    dt = 1.0 / sample_fps
    obs = pd.DataFrame(observations, columns=COLUMNS).astype({"detected": bool, "facing": bool, "motion": float})
    presence = obs[obs.detected].groupby("track_id").size() * dt
    # sustained presence filters out people who only pass through and spurious detections
    confirmed = presence[presence >= min_presence].index
    obs = obs[obs.track_id.isin(confirmed)].copy()
    obs["active"] = obs.motion >= still_threshold
    obs["interval"] = (obs.t // interval).astype(int)

    order = obs[obs.detected].groupby("track_id").t.min().sort_values().index
    names = {tid: f"P{n:02d}" for n, tid in enumerate(order, 1)}

    participants = []
    for tid in order:
        g = obs[obs.track_id == tid]
        det = g[g.detected]
        attention, activity = g.facing.mean(), g.active.mean()
        participants.append({
            "id": names[tid],
            "status": "Present",
            "first_seen": fmt_time(det.t.min()),
            "last_seen": fmt_time(det.t.max()),
            "present_s": round(len(det) * dt, 1),
            "presence_pct": round(100 * min(1.0, len(det) * dt / duration), 1) if duration else 0.0,
            "attention_pct": round(100 * attention, 1),
            "active_pct": round(100 * activity, 1),
            "longest_inactive_s": round(_longest_run((~g.facing & ~g.active).to_numpy()) * dt, 1),
            "engagement": score(attention, activity),
        })

    speech = None
    if audio is not None:
        times, _, active = audio
        speech = pd.Series(active).groupby((times // interval).astype(int)).mean()

    timeline = []
    for b in range(max(1, int(np.ceil(duration / interval)))):
        g = obs[obs.interval == b]
        sp = None if speech is None else float(speech.get(b, 0.0))
        row = {
            "start": fmt_time(b * interval),
            "end": fmt_time(min(duration, (b + 1) * interval)),
            "start_s": b * interval,
            "headcount": int(g[g.detected].track_id.nunique()),
            "attention": None, "activity": None, "speech": None if sp is None else round(sp, 3),
            "engagement": None,
        }
        if not g.empty:
            row["attention"] = round(float(g.facing.mean()), 3)
            row["activity"] = round(float(g.active.mean()), 3)
            row["engagement"] = score(row["attention"], row["activity"], sp)
        timeline.append(row)

    scored = [r["engagement"] for r in timeline if r["engagement"] is not None]
    session = {
        "duration": fmt_time(duration),
        "duration_s": round(duration, 1),
        "participants": len(participants),
        "avg_engagement": round(sum(scored) / len(scored), 1) if scored else None,
        "interval_s": interval,
        "audio": audio is not None,
    }
    return {"session": session, "participants": participants, "timeline": timeline}
