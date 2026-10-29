"""Rule based teaching assistant that turns session analytics into suggestions.

Runs fully offline. Suggestions are advisory only; the instructor decides what to act on.
"""


def _tip(level, title, detail):
    return {"level": level, "title": title, "detail": detail}


def _runs(rows, pred, min_len=1):
    """Yield (start, end) labels for consecutive rows where pred(row) holds for at least min_len rows."""
    run = []
    for r in rows + [None]:
        if r is not None and pred(r):
            run.append(r)
            continue
        if len(run) >= min_len:
            yield run[0]["start"], run[-1]["end"]
        run = []


def _mean(values):
    return sum(values) / len(values)


def suggest(report):
    rows = [r for r in report["timeline"] if r["engagement"] is not None]
    if not rows:
        return [_tip("info", "No participants detected",
                     "Check camera placement and lighting so faces are clearly visible, then run the analysis again.")]
    tips = []
    mean = _mean([r["engagement"] for r in rows])
    has_speech = report["session"]["audio"]

    if mean < 50:
        tips.append(_tip("warning", "Overall engagement is low",
                         f"Average engagement was {mean:.0f}/100. Break content into shorter segments and add "
                         "active learning such as think-pair-share, quick polls or short problem solving tasks."))

    for start, end in _runs(rows, lambda r: r["engagement"] < mean - 15):
        tips.append(_tip("warning", f"Attention dip {start} to {end}",
                         "Engagement fell well below the session average. Try a quick check for understanding, "
                         "a question to the room or a change of activity at this point."))

    third = len(rows) // 3
    if third:
        early, late = _mean([r["engagement"] for r in rows[:third]]), _mean([r["engagement"] for r in rows[-third:]])
        if late < early - 10:
            tips.append(_tip("warning", "Engagement declined over the session",
                             f"Engagement dropped from {early:.0f} in the first third to {late:.0f} in the last third. "
                             "Consider a short break or a switch in activity around the midpoint."))

    if has_speech:
        for start, end in _runs(rows, lambda r: r["speech"] >= 0.8 and r["engagement"] < mean, min_len=2):
            tips.append(_tip("suggestion", f"Long uninterrupted talk {start} to {end}",
                             "Continuous speech with below average engagement suggests a long monologue. "
                             "Pause to invite questions or ask students to summarize the key point."))
        for start, end in _runs(rows, lambda r: r["speech"] <= 0.1 and r["attention"] < 0.4):
            tips.append(_tip("suggestion", f"Quiet stretch with low attention {start} to {end}",
                             "The room was quiet and few students were facing forward. If this was independent "
                             "work, circulate and check that students are on task."))
        for start, end in _runs(rows, lambda r: r["speech"] >= 0.6 and r["attention"] < 0.4):
            tips.append(_tip("suggestion", f"Possible side conversations {start} to {end}",
                             "High audio activity combined with low forward attention can indicate off task talk. "
                             "Consider regrouping the class or giving a structured discussion prompt."))

    peak = max(r["headcount"] for r in rows)
    if peak >= 2 and rows[-1]["headcount"] < 0.75 * peak:
        tips.append(_tip("info", "Participants left before the end",
                         f"Headcount fell from a peak of {peak} to {rows[-1]['headcount']} in the final interval. "
                         "Check whether the session ran long or whether the ending could be more focused."))

    low = [p["id"] for p in report["participants"] if p["engagement"] < 40]
    if low:
        tips.append(_tip("info", f"{len(low)} participant(s) with low engagement",
                         f"{', '.join(low)} showed low engagement. A brief, private check in may help."))

    best = max(rows, key=lambda r: r["engagement"])
    if len(rows) > 1 and best["engagement"] > mean + 10:
        tips.append(_tip("positive", f"Engagement peak {best['start']} to {best['end']}",
                         "This was the most engaged part of the session. Note what was happening (a demo, "
                         "discussion or activity) and reuse that approach."))

    if not tips:
        tips.append(_tip("positive", "Engagement was steady",
                         f"Average engagement was {mean:.0f}/100 with no major dips. Keep the current pacing."))
    return tips
