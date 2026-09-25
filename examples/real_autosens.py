"""How far oref's sensitivity ratio moves in real users, per person over 28 days.

The question this answers is whether the simulated person drifts in insulin sensitivity the
way a real person does, read through the one instrument both sides share: oref's autosens
ratio. The ratio is logged on every oref cycle in the OpenAPS Data Commons devicestatus
records (`openaps.suggested.sensitivityRatio`), and the simulated oref0 SMB arm computes the
same quantity each cycle with the Oref1 arithmetic in `timsim/controller/autosens.py`. Where
the two distributions differ, the simulated person's day-to-day and multi-day sensitivity
terms (`timsim/patient/varying.py`, `INTERDAY_CV` and `SLOW_CV`) are the first place to look,
and `examples/sim_autosens.py` checks by ablation that the statistic can see those terms at
all.

The reason to ask now is practical. A change to an algorithm that acts only when autosens
reads resistant, such as Boost's autosens-at-target change of 24 September 2026
(Boost-AAPS-core 6812ef3e25), can only be evaluated on a bench whose people read resistant
about as often as real people do. If the bench rarely reads resistant, a paired run of that
change returns a null by construction, which is what happened with the Boost hypo model on 7
September 2026 (`examples/hypo_damper_reach.py`).

Method. Each user's devicestatus exports are streamed and every document carrying an oref
suggestion with a `sensitivityRatio` is kept, one per five-minute cycle. Cycles under a
temporary target, reconstructed from the user's `Temporary Target` treatments with a zero
duration read as a cancellation, are dropped, because oref lets a temporary target replace the
autosens ratio when `high_temptarget_raises_sensitivity` or its low counterpart is on and
nothing in the export says whether it was. One 28-day window per user, the one carrying the most
cycles among 40 evenly spaced starts, is admitted when it carries at least 70 per cent of its
8064 cycles. `examples/commons_cohort.py` takes the middle window and keeps the densest as a
check; here the densest is primary because the devicestatus records are gappier than the
glucose records, a test on one user finding an empty middle window in a record of 84 days
spread over thirteen months, and nothing about the ratio depends on where in the record the
window falls. A user whose ratio sits at exactly 1.0 on every admitted cycle is
counted as having autosens off and reported separately rather than pooled, since the simulated
arm always runs it.

Ratios are clipped to 0.7 to 1.2 before any statistic, the range the simulated arm runs,
because users may widen autosens_min and autosens_max and the simulated arm cannot follow
them. The share of cycles that needed clipping is reported.

Per person: the share of cycles reading resistant (ratio above 1.0) and sensitive (below
1.0), the 10th, 50th and 90th percentiles of the ratio, and the standard deviation across days
of the daily mean ratio. Summarised across people as median, mean and range, and 10th to 90th
percentile, which is the band the simulated cohort median is read against.

Registered before either side was run, 25 September 2026.

Expectation. The simulated arm reads sensitive far more than resistant: on the August panel
(`oref_autosens_on.json`) its per-subject median share below 1.0 was 26.5 per cent and its
median ratio 1.0, with the maximum reaching 1.2 in only some subjects. No real figure has been
measured in this package, so no expectation is registered for the real side.

Rule. For each of the share reading resistant, the share reading sensitive, the p10 to p90
width of the ratio and the day-to-day standard deviation, the simulated cohort median is
called inside when it lies within the real 10th to 90th percentile across users, and below or
above otherwise. The comparison is void for any statistic that the ablation arm in
`sim_autosens.py` does not move by more than its own paired interval, since that statistic
cannot see the sensitivity terms. If the share reading resistant is below the real band, the
bench cannot evaluate a change that acts on resistance, and `docs/READING_A_RESULT.md` gains a
row saying so. If it is inside, a bridge to the full Boost engine is justified as the next
piece of work, since the adapter in `controller/boost.py` reconstructs the base dose in Python
and cannot see the change.

Result, 25 September 2026 (`real_autosens.json`, `sim_autosens.json`). Of 240 users, 54 were
admitted: 125 have no oref ratio in their records (63 of them no devicestatus at all, the rest
on oref versions that do not log it), 57 lacked a 28-day window at 70 per cent coverage and 4 ran
with autosens off. The simulated shipped arm reproduced the oref0 SMB column of
`driver_ranking.json` exactly, largest time-in-range discrepancy 0.0 over 38 runs.

    per person, median (real p10 to p90)   simulated   real
    reading resistant, % of cycles          0.43       42.2 (10.7 to 70.2)   below
    reading sensitive, % of cycles          29.5       12.2 (1.8 to 44.7)    inside
    at exactly 1.0, % of cycles             69.8       36.4 (17.4 to 73.7)   inside
    ratio p90                               1.00       1.20 (1.01 to 1.20)   below
    ratio p10 to p90 width                  0.205      0.200 (0.119 to 0.347) inside
    day-to-day SD of the daily mean         0.049      0.064 (0.035 to 0.094) inside

Twelve of the forty simulated subjects never read resistant, and the highest reads it on 11.3
per cent of cycles, near the real 10th percentile. The ablation moved outcomes (time in range by
a median 2.0 points per subject, insulin by 3.0 U/day) and moved no ratio statistic by more than
its interval, so under the rule every statistic is void as a test of the sensitivity terms:
the simulated autosens does not follow the day-to-day and multi-day drift in `varying.py`. That
is a statement about the drift terms and does not rescue the resistant share, which describes
what the oref arm experiences whatever causes it.

So the rule's first consequence applies. The bench reads resistant about a hundredth as often
as real users, and a change acting only on resistance, Boost 6812ef3e25 included, has almost
nothing to act on here. The bridge to the full Boost engine is not built for it.
`examples/autosens_diagnostics.py` excludes the rig: the activity clamp moves the resistant share
by at most 0.66 points, and 34 to 65 per cent of cycles count as non-meal. What remains is that
the simulated person's fasting deviations centre on zero, where real users' glucose rises more
than their insulin predicts. The cause of that is not measured here.

    python examples/real_autosens.py
"""
import glob
import json
import multiprocessing as mp
import os
import re
import sys
import time
from datetime import datetime

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance

ROOT = os.path.expanduser("~/oref-investigations/240 NS samples")
OUT = os.path.join(MEASUREMENTS, "real_autosens.json")
WORKERS = 7
WINDOW_DAYS = 28
CYCLE_MS = 5 * 60_000
EXPECTED = WINDOW_DAYS * 288
MIN_COVERAGE = 0.70
CLIP = (0.7, 1.2)

_TT = re.compile(r'\{[^{}]*"Temporary Target"[^{}]*\}')
_DEC = json.JSONDecoder()


def _epoch_ms(value):
    """A Nightscout timestamp, as either epoch milliseconds or an ISO string, to epoch ms."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        v = int(value)
        return v if v > 1_000_000_000_000 else v * 1000
    s = str(value).strip()
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return int(datetime.fromisoformat(s).timestamp() * 1000)
    except ValueError:
        return None


def documents(path, needle):
    """Each top-level document of a JSON array export that contains `needle`, streamed.

    The largest devicestatus exports run to a gigabyte, and loading one whole takes several
    times that in memory, so the array is walked object by object with the standard decoder
    and only documents containing the needle are decoded at all.
    """
    buf = ""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        while True:
            chunk = fh.read(1 << 22)
            buf += chunk
            pos = 0
            while True:
                start = buf.find("{", pos)
                if start < 0:
                    buf = ""
                    break
                try:
                    obj, end = _DEC.raw_decode(buf, start)
                except json.JSONDecodeError:
                    if chunk and len(buf) - start < (1 << 26):
                        buf = buf[start:]  # incomplete, wait for more text
                        break
                    pos = start + 1        # malformed rather than incomplete: step past it
                    continue
                if needle in buf[start:end]:
                    yield obj
                pos = end
            if not chunk:
                return


def ratios_for(user_dir):
    """(epoch_ms, ratio) for every oref cycle in one user's devicestatus, one per cycle."""
    got = {}
    for path in sorted(glob.glob(os.path.join(user_dir, "**", "*devicestatus*.json"),
                                 recursive=True)):
        try:
            for doc in documents(path, '"sensitivityRatio"'):
                o = doc.get("openaps") if isinstance(doc, dict) else None
                if not isinstance(o, dict):
                    continue
                s = o.get("suggested") or o.get("enacted")
                if not isinstance(s, dict) or s.get("sensitivityRatio") is None:
                    continue
                t = _epoch_ms(s.get("timestamp") or s.get("deliverAt") or doc.get("created_at"))
                try:
                    r = float(s["sensitivityRatio"])
                except (TypeError, ValueError):
                    continue
                if t is None or not np.isfinite(r) or r <= 0:
                    continue
                got.setdefault(t // CYCLE_MS, (t, r))
        except Exception as exc:                  # a truncated export is not fatal
            print(f"  skip {os.path.basename(path)}: {exc}", file=sys.stderr)
    if not got:
        return None
    a = np.array(sorted(got.values()), dtype=float)
    return a


def temp_targets(user_dir):
    """Temporary target intervals as (start_ms, end_ms), with cancellations applied."""
    events = []
    for path in glob.glob(os.path.join(user_dir, "**", "*treatments*.json"), recursive=True):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        for m in _TT.finditer(text):
            try:
                d = json.loads(m.group(0))
            except json.JSONDecodeError:
                continue
            t = _epoch_ms(d.get("created_at") or d.get("timestamp"))
            if t is None:
                continue
            events.append((t, float(d.get("duration") or 0.0)))
    events.sort()
    out = []
    for i, (t, dur) in enumerate(events):
        if dur <= 0:
            continue
        end = t + dur * 60_000
        if i + 1 < len(events):               # a later target or a cancel ends this one
            end = min(end, events[i + 1][0])
        out.append((t, end))
    return out


def per_person(a):
    """The statistics for one 28-day window of (epoch_ms, ratio) rows, clipped."""
    raw = a[:, 1]
    r = np.clip(raw, *CLIP)
    day = ((a[:, 0] - a[0, 0]) // 86_400_000).astype(int)
    daily = np.array([r[day == d].mean() for d in np.unique(day) if (day == d).sum() >= 144])
    return {"cycles": int(len(r)),
            "resistant_pct": float(100.0 * np.mean(r > 1.0)),
            "sensitive_pct": float(100.0 * np.mean(r < 1.0)),
            "at_one_pct": float(100.0 * np.mean(r == 1.0)),
            "p10": float(np.percentile(r, 10)), "p50": float(np.percentile(r, 50)),
            "p90": float(np.percentile(r, 90)),
            "width_p10_p90": float(np.percentile(r, 90) - np.percentile(r, 10)),
            "daily_sd": float(daily.std(ddof=1)) if daily.size > 2 else None,
            "days_for_daily": int(daily.size),
            "clipped_pct": float(100.0 * np.mean((raw < CLIP[0]) | (raw > CLIP[1]))),
            "raw_min": float(raw.min()), "raw_max": float(raw.max())}


def one(user_dir):
    uid = os.path.basename(user_dir)
    t0 = time.time()
    a = ratios_for(user_dir)
    if a is None:
        return uid, {"status": "no_oref_ratio"}
    span = WINDOW_DAYS * 86_400_000
    t_lo, t_hi = a[0, 0], a[-1, 0]
    if t_hi - t_lo < span:
        return uid, {"status": "short_record", "cycles": int(len(a))}
    starts = np.linspace(t_lo, t_hi - span, 40)
    counts = [np.sum((a[:, 0] >= s) & (a[:, 0] < s + span)) for s in starts]
    start = float(starts[int(np.argmax(counts))])
    sel = a[(a[:, 0] >= start) & (a[:, 0] < start + span)]
    tts = temp_targets(user_dir)
    keep = np.ones(len(sel), bool)
    for s, e in tts:
        keep &= ~((sel[:, 0] >= s) & (sel[:, 0] < e))
    under_tt = float(100.0 * (1.0 - keep.mean())) if len(sel) else 0.0
    sel = sel[keep]
    cov = len(sel) / EXPECTED
    if cov < MIN_COVERAGE:
        return uid, {"status": "sparse_window", "coverage": round(cov, 3)}
    row = {"status": "admitted", "coverage": round(cov, 3),
           "under_temp_target_pct": under_tt,
           "record_days": round((t_hi - t_lo) / 86_400_000, 1),
           "seconds": round(time.time() - t0, 1)}
    if np.all(sel[:, 1] == 1.0):
        row["status"] = "autosens_off"
        return uid, row
    row.update(per_person(sel))
    return uid, row


def summary(values):
    v = np.asarray([x for x in values if x is not None], float)
    return {"n": int(v.size), "median": float(np.median(v)), "mean": float(np.mean(v)),
            "min": float(v.min()), "max": float(v.max()),
            "p10": float(np.percentile(v, 10)), "p90": float(np.percentile(v, 90))}


STATS = ("resistant_pct", "sensitive_pct", "at_one_pct", "p10", "p50", "p90",
         "width_p10_p90", "daily_sd", "clipped_pct")


def main():
    users = sorted(d for d in glob.glob(os.path.join(ROOT, "*")) if os.path.isdir(d))
    print(f"{len(users)} user directories, {WORKERS} workers", flush=True)
    t0 = time.time()
    with mp.Pool(WORKERS) as pool:
        rows = dict(pool.imap_unordered(one, users, chunksize=1))
    print(f"read in {(time.time() - t0) / 60:.1f} min", flush=True)
    status = {}
    for r in rows.values():
        status[r["status"]] = status.get(r["status"], 0) + 1
    print("status:", status)
    adm = {u: r for u, r in rows.items() if r["status"] == "admitted"}
    stats = {k: summary(r[k] for r in adm.values()) for k in STATS}
    for k, s in stats.items():
        print(f"  {k:>16}: median {s['median']:.3f}, mean {s['mean']:.3f}, "
              f"p10-p90 {s['p10']:.3f} to {s['p90']:.3f}, range {s['min']:.3f} to {s['max']:.3f}"
              f" (n {s['n']})")
    json.dump({"provenance": provenance.stamp(), "root": ROOT, "window_days": WINDOW_DAYS,
               "min_coverage": MIN_COVERAGE, "clip": CLIP, "status": status, "stats": stats,
               "users": rows}, open(OUT, "w"), indent=1)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
