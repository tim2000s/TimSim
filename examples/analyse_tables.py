"""Turn the run set into the paper's tables.

Medians are taken across the subjects completing both arms of the comparison being made,
since an arm that loses different subjects describes a different population. Paired
differences carry a 95 per cent interval from the paired standard error.
"""
import json
import os
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = json.load(open(os.path.join(REPO, "docs", "measurements", "paper_tables.json")))
idx = {(r["arm"], r["name"]): r for r in rows}
arms = sorted({r["arm"] for r in rows})
subjects = sorted({r["name"] for r in rows})

MEASURES = [("tir_cgm", "Time in range 70-180 mg/dL, %"),
            ("tbr70_cgm", "Time below 70 mg/dL, %"),
            ("tbr54_cgm", "Time below 54 mg/dL, %"),
            ("tar180_cgm", "Time above 180 mg/dL, %"),
            ("mean_cgm", "Mean sensor glucose, mg/dL"),
            ("cv_cgm", "Variability, CV %"),
            ("insulin_per_day", "Insulin, U/day"),
            ("rescue_per_30d", "Rescue helpings per 30 days")]


def completed(arm):
    return [n for n in subjects if idx.get((arm, n), {}).get("completed")]


def pair(a, b):
    return [n for n in subjects if idx.get((a, n), {}).get("completed")
            and idx.get((b, n), {}).get("completed")]


def table(a, b, title):
    keep = pair(a, b)
    print(f"\n### {title}")
    print(f"paired over {len(keep)} subjects completing both arms; "
          f"completion {len(completed(a))}/{len(subjects)} and "
          f"{len(completed(b))}/{len(subjects)}")
    print(f"| Measure | {a} | {b} | Paired difference, 95% |")
    print("|---|---|---|---|")
    for k, lab in MEASURES:
        va = np.array([idx[(a, n)][k] for n in keep], float)
        vb = np.array([idx[(b, n)][k] for n in keep], float)
        d = vb - va
        d = d[np.isfinite(d)]
        h = 1.96 * d.std(ddof=1) / np.sqrt(len(d)) if len(d) > 1 else float("nan")
        print(f"| {lab} | {np.median(va):.2f} | {np.median(vb):.2f} | "
              f"{d.mean():+.2f} +/- {h:.2f} |")


def terminations(arm):
    out = []
    for n in subjects:
        r = idx.get((arm, n))
        if r and not r.get("completed"):
            if "error" in r:
                out.append((n, "error", r["error"][:60]))
            else:
                out.append((n, "hyper" if r["final_bg"] > 250 else "hypo",
                            f"final {r['final_bg']:.0f} mg/dL"))
    return out


print(f"arms: {arms}")
print(f"subjects: {len(subjects)}")
for a in arms:
    c = completed(a)
    print(f"  {a:14} completed {len(c)}/{len(subjects)}")
    for n, kind, why in terminations(a):
        print(f"      {n:18} {kind:6} {why}")

table("trend_bare", "trend_layered", "Table 1: the correction loop, bench varied")
table("oref_bare", "oref_layered", "Table 2: oref0 SMB, bench varied")
table("oref_always", "oref_never", "Table 4: oref0 SMB, announcement withdrawn")

# The three announcement conditions side by side, on the subjects completing all three.
keep = [n for n in subjects
        if all(idx.get((a, n), {}).get("completed")
               for a in ("oref_always", "oref_layered", "oref_never"))]
print(f"\n### Announcement conditions, {len(keep)} subjects completing all three")
print("| Measure | always | some | never |")
print("|---|---|---|---|")
for k, lab in MEASURES:
    vals = [np.median([idx[(a, n)][k] for n in keep])
            for a in ("oref_always", "oref_layered", "oref_never")]
    print(f"| {lab} | " + " | ".join(f"{v:.2f}" for v in vals) + " |")
