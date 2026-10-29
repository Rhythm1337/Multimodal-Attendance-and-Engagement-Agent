"""Streamlit dashboard: streamlit run app.py"""
import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from engagement_agent import analyze
from engagement_agent.demo import demo_report

st.set_page_config(page_title="Attendance and Engagement Agent", layout="wide")
st.title("Multimodal Attendance and Engagement Agent")
st.caption("Privacy preserving classroom analytics. Video is processed locally and never stored or uploaded "
           "elsewhere. Participants are tracked by anonymous IDs only.")

with st.sidebar:
    st.header("Settings")
    interval = st.slider("Engagement interval (seconds)", 10, 300, 60, step=10)
    min_presence = st.slider("Minimum presence to mark attendance (seconds)", 1, 120, 10)
    sample_fps = st.slider("Frames analyzed per second", 1, 15, 5)

video = st.file_uploader("Session video", type=["mp4", "mov", "avi", "mkv", "webm"])
audio = st.file_uploader("Optional separate audio (otherwise the video's audio track is used)",
                         type=["wav", "mp3", "m4a", "ogg", "flac"])

if st.button("No video? Run a simulated demo session"):
    st.session_state.report = demo_report(interval=interval)

if video and st.button("Analyze session", type="primary"):
    with tempfile.TemporaryDirectory() as tmp:
        video_path = Path(tmp) / f"video{Path(video.name).suffix}"
        video_path.write_bytes(video.getbuffer())
        audio_path = None
        if audio:
            audio_path = Path(tmp) / f"audio{Path(audio.name).suffix}"
            audio_path.write_bytes(audio.getbuffer())
        bar = st.progress(0.0, text="Analyzing video")
        try:
            st.session_state.report = analyze(str(video_path), audio_path and str(audio_path), sample_fps,
                                              interval, min_presence, progress=bar.progress)
        except ValueError as e:
            st.error(str(e))
        bar.empty()

report = st.session_state.get("report")
if report:
    s = report["session"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Duration", s["duration"])
    c2.metric("Participants present", s["participants"])
    c3.metric("Average engagement", "n/a" if s["avg_engagement"] is None else f"{s['avg_engagement']:.0f}/100")
    c4.metric("Audio analyzed", "Yes" if s["audio"] else "No")

    st.subheader("Teaching suggestions")
    show = {"warning": st.warning, "suggestion": st.info, "info": st.info, "positive": st.success}
    for tip in report["suggestions"]:
        show[tip["level"]](f"**{tip['title']}**  \n{tip['detail']}")

    timeline = pd.DataFrame(report["timeline"])
    st.subheader("Engagement over time")
    st.line_chart(timeline.set_index("start")[["engagement"]])
    cols = ["attention", "activity"] + (["speech"] if s["audio"] else [])
    st.caption("Signal breakdown (share of observations): attention = facing forward, activity = visible "
               "movement, speech = audio activity")
    st.line_chart(timeline.set_index("start")[cols])

    st.subheader("Attendance and participant analytics")
    participants = pd.DataFrame(report["participants"])
    st.dataframe(participants, hide_index=True)

    st.subheader("Interval details")
    st.dataframe(timeline.drop(columns="start_s"), hide_index=True)

    d1, d2, d3 = st.columns(3)
    d1.download_button("Download report (JSON)", json.dumps(report, indent=2), "report.json", "application/json")
    d2.download_button("Download attendance (CSV)", participants.to_csv(index=False), "attendance.csv", "text/csv")
    d3.download_button("Download timeline (CSV)", timeline.to_csv(index=False), "timeline.csv", "text/csv")
