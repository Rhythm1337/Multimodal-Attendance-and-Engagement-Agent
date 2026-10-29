"""Simulated classroom session so the analytics and suggestions can be explored without a video."""
import numpy as np

from .advisor import suggest
from .analytics import build_report


def demo_report(minutes=30, students=12, sample_fps=2.0, interval=60, seed=0):
    """Report for a simulated lecture: steady start, mid session dip, late decline, several early leavers."""
    rng = np.random.default_rng(seed)
    duration = minutes * 60.0
    times = np.arange(0, duration, 1 / sample_fps)
    phase = times / duration
    # class wide attention curve: high at start, dip around 40 percent, decline in the final quarter
    base = 0.9 - 0.5 * np.exp(-((phase - 0.4) / 0.06) ** 2) - 0.5 * np.clip(phase - 0.75, 0, None) * 4
    observations = []
    for sid in range(1, students + 1):
        focus = 0.35 if sid in (4, 9) else 1.0
        leave = 0.7 * duration if sid in (7, 10, 11, 12) else duration
        for t, p in zip(times, base):
            if t >= leave:
                break
            observations.append({
                "t": round(float(t), 2), "track_id": sid, "detected": bool(rng.random() < 0.9),
                "facing": bool(rng.random() < p * focus), "motion": float(rng.uniform(0, 0.04)),
            })
    windows = np.arange(0, duration, 0.5)
    # lecture with continuous talk, then a discussion with mixed audio in the middle
    talk = np.where((windows > 0.45 * duration) & (windows < 0.6 * duration), 0.5, 0.9)
    active = rng.random(len(windows)) < talk
    report = build_report(observations, duration, (windows, active.astype(float), active), sample_fps, interval)
    report["suggestions"] = suggest(report)
    return report
