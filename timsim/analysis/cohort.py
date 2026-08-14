"""Comparing arms honestly: the same people in every column, and failures explained.

Two rules that cost this package wrong answers before they were written down.

An arm that loses different subjects is a different population, so a comparison between arms
has to be restricted to the subjects completing all of them. Reporting each arm's own median
over its own survivors compares different people and hides the difference, and the direction of
the bias is always favourable, because the runs that fail are the ones that went furthest
wrong.

A completion count says how many runs ended early and nothing about why, and the two failure
modes here are opposites. A run ending at 10 mg/dL is the model having no floor under a falling
glucose; a run ending at 600 is insulin that never arrived. Reporting them together as
`16/21 completed` averages a hypoglycaemia problem with a hyperglycaemia one. Under oref0 SMB
on the layered bench, five of seven terminations were hyperglycaemic, which is the opposite of
what a completion count invites a reader to assume.
"""
import numpy as np

# Where the underlying model stops being defined, which is what ends a run.
LOW_LIMIT = 10.0
HIGH_LIMIT = 600.0
# A termination is read as hypoglycaemic or hyperglycaemic by which end it left from.
LOW_TERMINATION = 40.0
HIGH_TERMINATION = 500.0


def paired_subjects(rows, key=lambda r: (r.get("arm") or r.get("controller"), r.get("bench"))):
    """Subjects completing every arm present, and the arms they were found in.

    Raises when no subject completes every arm, because a comparison is then not available
    and producing one from partial overlap would be inventing a population.
    """
    arms = sorted({key(r) for r in rows})
    per_arm = {a: {r["name"] for r in rows if key(r) == a and r.get("completed")} for a in arms}
    common = set.intersection(*per_arm.values()) if per_arm else set()
    if not common:
        raise ValueError(
            "no subject completed every arm, so the arms cannot be compared on a common "
            f"population; per-arm completers were { {a: len(s) for a, s in per_arm.items()} }")
    return sorted(common), arms


def classify_termination(result):
    """Why one run ended early, from what the run itself recorded.

    Returns None for a run that completed. The site fields are present only when the site
    layer was on, and a failure in progress at the end is reported because a run that ends
    while insulin is not arriving has a different explanation from one that ends otherwise.
    """
    if getattr(result, "completed", True):
        return None
    bg = np.asarray(getattr(result, "bg", []), dtype=float)
    if not len(bg):
        return {"direction": "unknown", "reason": "no readings"}
    final = float(bg[-1])
    meta = dict(getattr(result, "meta", {}) or {})
    step = float(getattr(result, "sample_time", 5.0))
    day = len(bg) * step / 1440.0

    if final <= LOW_TERMINATION:
        direction, reason = "hypoglycaemic", "glucose left the model's range from below"
    elif final >= HIGH_TERMINATION:
        direction, reason = "hyperglycaemic", "glucose left the model's range from above"
    else:
        direction, reason = "unknown", "ended without reaching either limit"

    out = {"direction": direction, "reason": reason, "day_ended": round(day, 2),
           "final_bg": round(final, 1), "lowest_bg": round(float(np.min(bg)), 1),
           "highest_bg": round(float(np.max(bg)), 1)}

    ins = np.asarray(getattr(result, "insulin_series", []), dtype=float)
    if len(ins):
        n = max(int(60.0 / step), 1)
        out["insulin_last_hour_u"] = round(float(np.sum(ins[-n:])), 2)
        out["insulin_last_six_hours_u"] = round(float(np.sum(ins[-6 * n:])), 2)

    if "site_failures" in meta:
        out["site_failures"] = meta.get("site_failures")
        out["site_units_lost"] = round(float(meta.get("site_units_lost") or 0.0), 1)
        out["site_failed_hours"] = round(float(meta.get("site_failed_minutes") or 0.0) / 60.0, 1)
        out["site_failing_at_end"] = bool(meta.get("site_failing_at_end"))
        if out["site_failing_at_end"]:
            out["reason"] += ", with the infusion site not absorbing at the time"

    rescues = [x for x in getattr(result, "rescue_log", ()) or ()]
    if rescues:
        end = len(bg) * step
        out["rescues_last_six_hours"] = sum(1 for x in rescues if float(x[0]) >= end - 360.0)
    return out


def failure_report(runs):
    """A per-arm account of what ended early and why, for printing beside any comparison.

    `runs` is an iterable of dicts carrying at least `name`, `completed` and either `arm` or
    `controller`, plus whatever `classify_termination` produced under `termination`.
    """
    out = {}
    for r in runs:
        arm = r.get("arm") or r.get("controller") or ""
        rec = out.setdefault(arm, {"n": 0, "completed": 0, "hypoglycaemic": 0,
                                   "hyperglycaemic": 0, "unknown": 0, "with_site_failing": 0,
                                   "subjects": []})
        rec["n"] += 1
        if r.get("completed"):
            rec["completed"] += 1
            continue
        t = r.get("termination") or {}
        rec[t.get("direction", "unknown")] = rec.get(t.get("direction", "unknown"), 0) + 1
        if t.get("site_failing_at_end"):
            rec["with_site_failing"] += 1
        rec["subjects"].append({"name": r.get("name"), **t})
    return out


def format_failure_report(report):
    """The report as lines, so every comparison can print why runs ended rather than how many."""
    lines = []
    for arm in sorted(report):
        r = report[arm]
        lines.append(f"{arm}: {r['completed']}/{r['n']} completed"
                     + ("" if r["completed"] == r["n"] else
                        f"; {r['hypoglycaemic']} ended low, {r['hyperglycaemic']} ended high"
                        + (f", {r['unknown']} unclassified" if r["unknown"] else "")
                        + (f"; {r['with_site_failing']} with the site not absorbing"
                           if r["with_site_failing"] else "")))
        for s in r["subjects"]:
            lines.append(f"    {s.get('name','?'):>15}  day {s.get('day_ended','?')}"
                         f"  final {s.get('final_bg','?')} mg/dL  {s.get('reason','')}")
    return "\n".join(lines)


__all__ = ["paired_subjects", "classify_termination", "failure_report",
           "format_failure_report", "LOW_TERMINATION", "HIGH_TERMINATION"]
