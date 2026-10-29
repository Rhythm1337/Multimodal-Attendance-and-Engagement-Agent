"""Command line interface: python -m engagement_agent <video or webcam index> [options]"""
import argparse

from .pipeline import analyze, save_report


def main():
    p = argparse.ArgumentParser(description="Analyze attendance and engagement for a classroom session.")
    p.add_argument("source", help="path to a video file, or a webcam index such as 0 for a live session")
    p.add_argument("--audio", help="separate audio file (defaults to the video's own audio track)")
    p.add_argument("--out", default="reports", help="output directory (default: reports)")
    p.add_argument("--interval", type=int, default=60, help="engagement interval in seconds (default: 60)")
    p.add_argument("--min-presence", type=float, default=10.0,
                   help="seconds a person must be seen to be marked present (default: 10)")
    p.add_argument("--fps", type=float, default=5.0, help="frames analyzed per second (default: 5)")
    p.add_argument("--max-seconds", type=float, help="stop after this many seconds (required for webcam)")
    args = p.parse_args()

    source = int(args.source) if args.source.isdigit() else args.source
    if isinstance(source, int) and not args.max_seconds:
        p.error("--max-seconds is required when reading from a webcam")

    report = analyze(source, args.audio, args.fps, args.interval, args.min_presence, args.max_seconds)
    out = save_report(report, args.out)

    s = report["session"]
    print(f"Duration: {s['duration']}  Participants present: {s['participants']}  "
          f"Average engagement: {s['avg_engagement']}  Audio: {'yes' if s['audio'] else 'no'}")
    for p_ in report["participants"]:
        print(f"  {p_['id']}  {p_['first_seen']} to {p_['last_seen']}  engagement {p_['engagement']}")
    print("Suggestions:")
    for tip in report["suggestions"]:
        print(f"  [{tip['level']}] {tip['title']}: {tip['detail']}")
    print(f"Reports written to {out}/")


if __name__ == "__main__":
    main()
