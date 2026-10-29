"""End to end session analysis: video and audio in, report with suggestions out."""
import json
from pathlib import Path

import pandas as pd

from .advisor import suggest
from .analytics import build_report
from .audio import load_audio, voice_activity
from .vision import analyze_video


def analyze(source, audio_path=None, sample_fps=5.0, interval=60, min_presence=10.0, max_seconds=None,
            progress=None):
    """Analyze a video file path or webcam index. Audio comes from audio_path, else from the video file."""
    observations, duration = analyze_video(source, sample_fps, max_seconds, progress=progress)
    audio = None
    audio_source = audio_path or (None if isinstance(source, int) else source)
    if audio_source:
        samples = load_audio(audio_source)
        if samples is not None and samples.size:
            audio = voice_activity(samples)
    report = build_report(observations, duration, audio, sample_fps, interval, min_presence)
    report["suggestions"] = suggest(report)
    return report


def save_report(report, out_dir):
    """Write report.json, attendance.csv and timeline.csv to out_dir and return the directory."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2))
    pd.DataFrame(report["participants"]).to_csv(out / "attendance.csv", index=False)
    pd.DataFrame(report["timeline"]).to_csv(out / "timeline.csv", index=False)
    return out
