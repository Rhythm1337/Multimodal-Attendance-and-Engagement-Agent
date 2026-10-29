# Multimodal Attendance and Engagement Agent

An AI powered, privacy preserving classroom intelligence system. It processes a recorded or live classroom video, tracks attendance based on sustained presence, fuses visual and audio signals into engagement trends, and generates teaching suggestions for the instructor. Everything runs offline on a local machine.

## Features

- **Automated attendance:** participants are detected and tracked across frames. A person is marked present only after a minimum amount of sustained presence (10 seconds by default), which filters out people passing through and false detections. First seen and last seen timestamps are recorded for each participant.
- **Engagement analysis:** head orientation (frontal vs. profile face), movement around each person, inactivity duration and audio activity are combined into an engagement score from 0 to 100 for every participant and every time interval.
- **Teaching suggestions:** a rule based agent reviews the session and points out attention dips, engagement decline over time, long monologues, quiet off task stretches, possible side conversations, early departures and engagement peaks worth repeating. Suggestions are advisory only.
- **Session analytics:** per participant and per interval tables, charts, and JSON or CSV exports.
- **Privacy by design:** no face recognition, no identity storage and no network calls. Participants get anonymous IDs (P01, P02, ...) that are only valid within one session. Uploaded videos are deleted once the analysis finishes.

## Architecture

```
video ──► vision.py ── face detection (Haar frontal + profile)
                     ── centroid tracking with anonymous IDs
                     ── per person motion (frame differencing)
                                    │
audio ──► audio.py ── ffmpeg decode ── energy based voice activity
                                    │
                                    ▼
                         analytics.py: fusion
               attendance, participant and interval engagement
                                    │
                                    ▼
                         advisor.py: teaching suggestions
                                    │
                     ┌──────────────┴──────────────┐
                     ▼                             ▼
          CLI (python -m engagement_agent)   Dashboard (app.py)
```

| Module | Responsibility |
| --- | --- |
| `engagement_agent/vision.py` | Frame sampling, face detection, tracking, head orientation and motion cues |
| `engagement_agent/audio.py` | Audio extraction with ffmpeg and voice activity detection |
| `engagement_agent/analytics.py` | Attendance filtering, engagement scoring and interval timeline |
| `engagement_agent/advisor.py` | Rule based teaching suggestions |
| `engagement_agent/pipeline.py` | End to end analysis and report export |
| `app.py` | Streamlit dashboard |

### Engagement score

For each observation of a participant:

- **Attention:** the face is detected looking forward (frontal face). Profile faces or a missing face while the person is still tracked (head down or turned away) count as not attentive.
- **Activity:** visible movement in the face and upper body region above a small threshold.
- **Speech:** the share of audio windows with voice activity in the interval.

```
with audio:     engagement = 100 * (0.6 * attention + 0.2 * activity + 0.2 * speech)
without audio:  engagement = 100 * (0.75 * attention + 0.25 * activity)
```

Participant scores use attention and activity only, since audio cannot be attributed to individuals.

## Setup

Requirements: Python 3.8 or later, and ffmpeg for audio analysis (video analysis works without it).

```bash
git clone https://github.com/Rhythm1337/Multimodal-Attendance-and-Engagement-Agent.git
cd Multimodal-Attendance-and-Engagement-Agent
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

### Dashboard

```bash
streamlit run app.py
```

Upload a session video, adjust the interval and attendance settings in the sidebar, and click **Analyze session**.

### Command line

```bash
# recorded session
python -m engagement_agent lecture.mp4 --interval 60 --out reports

# separate audio file
python -m engagement_agent lecture.mp4 --audio lecture.wav

# live webcam session for 10 minutes
python -m engagement_agent 0 --max-seconds 600
```

Options:

| Option | Default | Description |
| --- | --- | --- |
| `--audio` | video audio track | Separate audio file |
| `--out` | `reports` | Output directory |
| `--interval` | `60` | Engagement interval in seconds |
| `--min-presence` | `10` | Seconds of presence required to mark attendance |
| `--fps` | `5` | Frames analyzed per second |
| `--max-seconds` | none | Stop after this many seconds (required for webcam) |

Outputs written to the output directory:

- `report.json`: session summary, participants, timeline and suggestions
- `attendance.csv`: one row per participant with presence and engagement metrics
- `timeline.csv`: one row per interval with headcount, attention, activity, speech and engagement

## Tests

```bash
pytest
```

## Limitations

- Haar cascade detection works best with a front facing camera, good lighting and faces at least about 25 pixels wide.
- Participants are anonymous. Mapping IDs to student names would require face recognition with consent, which is intentionally left out.
- A person who leaves the frame for more than 10 seconds gets a new ID when they return.
- Voice activity uses an energy threshold and does not separate speakers.

## Tech stack

Python, OpenCV, NumPy, pandas, Streamlit, ffmpeg.
