"""The DCLP3 trial as a real, free-living, held-out reference.

Everything this package has been scored against until now is either four cohort medians per
statistic, or a cohort of Boost users who are also the people the algorithm work is aimed
at. Neither is held out, and neither is a randomised comparison.

DCLP3 is both. It is the pivotal trial of Control-IQ: 168 participants completed, 112
randomised to closed loop and 56 to sensor-augmented pump, followed for 26 weeks in free
living, with about 7.5 million CGM readings between them. It is publicly available from the
Jaeb Center, and it is not redistributed here for the same reason the virtual population is
not: point `DCLP3_DIR` at your own copy.

Two things it gives this package that nothing else has.

A held-out reference. Visentin et al. validated the simulator against a database explicitly
not used to develop it, and admitted their data was inpatient only, saying they had no
evidence performance would hold in outpatient free-living individuals and suggesting CGM
data as the way to find out. This is that data. `split` seals a fraction of participants
behind a fingerprint so they can be scored once, at the end, rather than tuned against.

A real known answer. Level 4 currently asks whether closing the loop improves time in range
by roughly the ten points the literature reports. DCLP3 randomised it. The comparison
between its two arms is the actual effect, measured on the same people, by the trial that
established it.
"""
import hashlib
import json
import os

import numpy as np

DCLP3_DIR = os.environ.get(
    "DCLP3_DIR",
    os.path.expanduser("~/Downloads/dclp3"))
DATA = "Data Files"
def cache_path(source="pump"):
    return os.path.join(DCLP3_DIR, f"timsim_cache_{source}.npz")


CACHE = os.path.join(DCLP3_DIR, "timsim_cache.npz")   # legacy Clarity cache

CLOSED_LOOP = "CLC"          # Control-IQ
PUMP = "SAP"                 # sensor-augmented pump, the control arm


def available():
    return os.path.isdir(os.path.join(DCLP3_DIR, DATA))


def _path(name):
    return os.path.join(DCLP3_DIR, DATA, name)


def roster():
    """Participants with their randomised arm. Only those who completed."""
    import pandas as pd
    r = pd.read_csv(_path("PtRoster_a.txt"), sep="|", encoding="utf-16")
    r = r[r.PtStatus == "Completed"]
    return r[["PtID", "trtGroup", "SiteID"]].reset_index(drop=True)


# Two CGM sources, and the difference between them matters more than it looks.
#
# `DexcomClarityCGM_a.txt` is the Clarity export. `Pump_CGMGlucoseValue.txt` is what the
# pump actually received, which is what a closed-loop algorithm acted on. On the same
# sensor, the same person and the same window, the Clarity export has a second-difference
# spread of 2.53 mg/dL against the pump's 5.28. Clarity smooths, by roughly a factor of two.
#
# The pump source is therefore the right one for this package, because everything here is
# about what an algorithm sees. Reading the Clarity export instead would have retired a
# sensor layer that is correct: the pump figure of 5.28, inter-quartile range 4.78 to 6.12,
# sits inside the 4.5 to 6.7 this package already uses.
#
# Smoothing does not only affect the noise statistic. It raises autocorrelation and
# suppresses the sharp reversing dips the compression detector looks for, so any statistic
# read off Clarity is suspect in a direction that is easy to mistake for a finding.
SOURCES = {
    "pump": ("Pump_CGMGlucoseValue.txt", "CGMValue", None),
    "clarity": ("DexcomClarityCGM_a.txt", "CGM", "utf-16"),
}
DEFAULT_SOURCE = "pump"


def build_cache(chunksize=1_000_000, verbose=True, source=DEFAULT_SOURCE):
    """Parse a CGM source once into a compact cache.

    Only the participant, the timestamp as epoch seconds, and the reading are kept.
    """
    import pandas as pd
    fname, col, enc = SOURCES[source]
    pt, ts, cgm = [], [], []
    reader = pd.read_csv(_path(fname), sep="|", encoding=enc,
                         usecols=["PtID", "DataDtTm", col], chunksize=chunksize)
    for i, chunk in enumerate(reader):
        chunk = chunk.rename(columns={col: "CGM"}).dropna(subset=["DataDtTm", "CGM"])
        t = pd.to_datetime(chunk["DataDtTm"], errors="coerce")
        ok = t.notna()
        pt.append(chunk["PtID"].to_numpy()[ok.to_numpy()].astype(np.int32))
        # Convert through datetime64[s] rather than dividing the integer view. pandas 3
        # returns microsecond resolution, so assuming nanoseconds is out by a thousand and
        # collapses every trace into a few minutes.
        ts.append(t[ok].to_numpy().astype("datetime64[s]").astype(np.int64))
        cgm.append(pd.to_numeric(chunk["CGM"], errors="coerce").to_numpy()[ok.to_numpy()])
        if verbose:
            print(f"  chunk {i + 1}: {sum(len(x) for x in pt):,} readings", flush=True)
    pt = np.concatenate(pt)
    ts = np.concatenate(ts)
    cgm = np.concatenate(cgm).astype(np.float32)
    good = np.isfinite(cgm) & (cgm > 0)
    pt, ts, cgm = pt[good], ts[good], cgm[good]
    order = np.lexsort((ts, pt))
    path = cache_path(source)
    np.savez_compressed(path, pt=pt[order], ts=ts[order], cgm=cgm[order])
    if verbose:
        print(f"cached {len(pt):,} readings from {source} to {path}")
    return path


def load(source=DEFAULT_SOURCE):
    """(participant ids, epoch seconds, mg/dL), sorted by participant then time."""
    path = cache_path(source)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"no cache at {path}. Build it with `python -m timsim.validation.dclp3`.")
    z = np.load(path)
    return z["pt"], z["ts"], z["cgm"]


def traces(arm=None, participants=None, min_days=7.0, max_gap_minutes=8.0,
           min_segment=288, source=DEFAULT_SOURCE):
    """Contiguous five-minute stretches per participant.

    A gap longer than `max_gap_minutes` ends a segment, so a break in wear is never read as
    a glucose excursion. Segments shorter than `min_segment` samples are dropped.
    """
    pt, ts, cgm = load(source)
    if participants is None and arm is not None:
        r = roster()
        participants = set(r.loc[r.trtGroup == arm, "PtID"])
    keep = np.isin(pt, list(participants)) if participants is not None else slice(None)
    pt, ts, cgm = pt[keep], ts[keep], cgm[keep]

    out = {}
    for p in np.unique(pt):
        m = pt == p
        t, g = ts[m], cgm[m]
        if (t[-1] - t[0]) / 86400.0 < min_days:
            continue
        breaks = np.where(np.diff(t) > max_gap_minutes * 60)[0]
        segs = []
        for lo, hi in zip(np.r_[0, breaks + 1], np.r_[breaks + 1, len(t)]):
            if hi - lo >= min_segment:
                segs.append((t[lo:hi], g[lo:hi]))
        if segs:
            out[int(p)] = segs
    return out


# ------------------------------------------------------------------ the sealed split
def split(seed=20260807, held_out_fraction=0.4):
    """Split participants into a calibration set and a sealed held-out set.

    Stratified by arm, so both halves carry closed-loop and pump participants in the trial's
    own proportions. The fingerprint is over the held-out identities, so a split can be
    recorded before any of it is looked at and checked afterwards. A held-out set that has
    been peeked at and reshuffled will not reproduce its fingerprint.
    """
    r = roster()
    rng = np.random.default_rng(seed)
    calib, held = [], []
    for arm in sorted(r.trtGroup.unique()):
        ids = np.sort(r.loc[r.trtGroup == arm, "PtID"].to_numpy())
        order = rng.permutation(len(ids))
        cut = int(round(len(ids) * (1.0 - held_out_fraction)))
        calib += sorted(int(i) for i in ids[order[:cut]])
        held += sorted(int(i) for i in ids[order[cut:]])
    payload = {"seed": seed, "held_out_fraction": held_out_fraction,
               "held_out": sorted(held)}
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    return {"calibration": sorted(calib), "held_out": sorted(held),
            "fingerprint": fingerprint, "seed": seed,
            "n_calibration": len(calib), "n_held_out": len(held)}


# ------------------------------------------------------------------ the reference
def signatures(arm=CLOSED_LOOP, participants=None, seed=0):
    """The eleven fidelity statistics computed on real traces, the same way as on ours.

    `drift` cannot be read off a glucose trace, since it is a property of the algorithm's
    settings rather than of the person, so it is absent rather than zero.
    """
    from ..analysis import signatures as S

    packed = []
    for segs in traces(arm=arm, participants=participants).values():
        for t, g in segs:
            packed.append(dict(t=t.astype(float) - float(t[0]), bg=g.astype(float),
                               hour=((t.astype(float) / 3600.0) % 24)))
    out = {}
    for i, (key, _, fn) in enumerate(S.SIGS):
        out[key] = S.boot_ci([fn(d) for d in packed], seed=seed + i)
    out["_segments"] = len(packed)
    out["_days"] = sum(len(d["bg"]) for d in packed) * 5.0 / 1440.0
    return out


def arm_outcomes(participants=None):
    """Time in range and below range per participant, by arm. The level 4 known answer."""
    r = roster()
    if participants is not None:
        r = r[r.PtID.isin(participants)]
    out = {}
    for arm in (CLOSED_LOOP, PUMP):
        ids = set(r.loc[r.trtGroup == arm, "PtID"])
        rows = []
        for p, segs in traces(participants=ids).items():
            g = np.concatenate([s[1] for s in segs])
            rows.append({"PtID": p,
                         "tir": float(100 * np.mean((g >= 70) & (g < 180))),
                         "tbr": float(100 * np.mean(g < 70)),
                         "tbr54": float(100 * np.mean(g < 54)),
                         "mean": float(g.mean()),
                         "cv": float(100 * g.std() / g.mean())})
        out[arm] = rows
    return out


# Measured on the calibration half only, with the other 67 participants sealed behind the
# fingerprint below. Read from the pump-received source, per participant, pooling each
# person's segments, which is the unit the four-cohort reference uses.
#
# Segment length matters and is worth recording. Computed per contiguous stretch instead of
# per participant, the diurnal amplitude reads 101 mg/dL rather than 48, because an
# hour-of-day mean estimated from one sensor session is noisy and a peak-to-trough measure
# inflates with that noise. There is no contiguous stretch beyond about ten days here, since
# sensor sessions end, so a simulator run as 28 unbroken days is not comparable unless the
# real data is pooled first.
SPLIT_FINGERPRINT = "b83cfe2addb9dc47"

# median [inter-quartile range] per participant, closed-loop arm, 67 participants,
# 10,754 days, median 164 days each.
REFERENCE = {
    "CLC": {"participants": 67, "days": 10754, "median_days_each": 164, "source": "pump",
            "cv": (33.37, 29.82, 36.98), "tail": (4.64, 3.38, 6.16),
            "acf30": (0.87, 0.85, 0.89), "acf60": (0.67, 0.62, 0.71),
            "outcome": (27.15, 24.04, 32.08), "diurnal": (47.97, 37.04, 61.11),
            "hypo_rec": (47.52, 38.72, 54.98), "hypo_reb": (45.97, 38.31, 53.23),
            "compress": (2.47, 1.68, 3.74), "noise": (5.04, 4.42, 5.57)},
}

# The same statistics off the Clarity export, kept because the gap between the two is the
# size of the error a smoothed source introduces.
REFERENCE_VIA_CLARITY = {
    "cv": 34.35, "tail": 3.10, "acf30": 0.89, "acf60": 0.71, "outcome": 26.07,
    "diurnal": 50.14, "hypo_rec": 55.00, "hypo_reb": 41.41, "compress": 1.66,
    "noise": 2.66,
}

# Second-difference spread on the same sensor, person and window, from both sources.
CLARITY_SMOOTHING = {"pump": 5.28, "clarity": 2.53, "ratio": 2.05, "participants": 49}

# What the participants' pumps were actually set to, from `InsulinPumpSettings_a.txt` on the
# 67 closed-loop calibration participants. Read `therapy_settings` for how it is derived.
#
# Two of these settled questions this package had left open.
#
# Basal is flat. Taking each participant's half-hourly profile relative to their own 24-hour
# mean, the population median sits between 0.97 and 1.03 at every hour of the day. There is
# no dawn shape in prescribed basal at population level, which is what this package assumes
# by default and had never checked.
#
# The correction factor does not agree, and the disagreement is not this package's. Taken at
# midday, so that a single time block is being compared with a single time block, DCLP3
# participants run a median of 35 mg/dL per unit (IQR 30 to 50). The generated subjects measure 14.7, the
# ten published adults measure 12.6, and simglucose's own settings table states 11.5 for
# them. Model and table agree with each other: `check_published_cohort_obeys_clinical_rules`
# puts the measured response at 1.10 times the stated factor. Both disagree with clinical
# practice by a factor near three. Applying the 1800 rule to the published subjects' own
# stated daily dose gives 30.6 against their tabulated 11.5.
#
# Carbohydrate ratio has no such problem: 8.0 in the trial at midday, 8.9 generated, 9.5
# published, 8.5 from the 500 rule on the same subjects. So the disagreement is confined to
# insulin, and it implies a glucose rise per gram of carbohydrate of about 1.9 mg/dL in the
# model against 4.17 taken per participant from the trial's own settings and 3.6 from the
# clinical rules.
#
# That is a limit on the physiology rather than a defect in this package, and it bounds what
# the behaviour layer can produce: a carbohydrate that is miscounted, unannounced or eaten
# to treat a low moves a virtual subject about half as far as it would move a real one.
#
# Whether the correction factor itself is a defect worth diverging from was tested and the
# answer is no. Roughly half of it is an operating-point artefact, since one unit moves a
# published adult 12.6 mg/dL from settled basal and 18.5 from 250 where a correction is
# actually given. The rest is settled by running the inference backwards: handing the
# algorithm the weaker factor real people run, 35 rather than 14.7, moves this simulator
# toward the trial rather than away from it. Real settings are conservative and real people
# under-correct, which is why their highs last longer. `simulate(..., isf_scale=2.4)`.
# `docs/FIDELITY.md` sets out both measurements.
THERAPY_SETTINGS = {
    "participants": 67,
    "basal_share_of_daily_dose": (0.50, 0.42, 0.57),
    "total_daily_insulin_u": (47.0, 34.4, 62.4),
    # median and interquartile range, read at midday
    "carb_ratio_g_per_u": (8.0, 7.0, 10.0),
    "correction_factor_mgdl_per_u": (35.0, 30.0, 50.0),
    "basal_relative_to_own_mean": {"min_over_hours": 0.97, "max_over_hours": 1.03},
    # per participant, then the median, rather than a ratio of two medians
    "mgdl_per_gram": {"dclp3": 4.17, "dclp3_iqr": (3.33, 5.00),
                      "clinical_500_1800_rule": 3.60,
                      "timsim_generated": 1.89, "published_adults": 1.98},
}

HALF_HOURLY_BASAL = [f"InsBasal{h:02d}{m:02d}" for h in range(24) for m in (0, 30)]


def ages(arm=CLOSED_LOOP, calibration_only=True):
    """Participant ages at enrolment.

    The only demographic the public release keeps. Weight, height and HbA1c are all
    stripped from `DiabScreening_a.txt`, so a cohort can be matched on age and on nothing
    else. The closed-loop calibration half has a median of 29, a range of 14 to 63, and is
    28% under 18, which is a different population from this package's 34 adults at a median
    of 49.
    """
    import pandas as pd

    d = pd.read_csv(_path("DiabScreening_a.txt"), sep="|", encoding="utf-16")
    keep = set(roster().query(f"trtGroup == '{arm}'").PtID)
    if calibration_only:
        keep &= set(split()["calibration"])
    a = pd.to_numeric(d.loc[d.PtID.isin(keep), "AgeAtEnrollment"], errors="coerce")
    return a.dropna().to_numpy(float)


def ages_by_participant(arm=CLOSED_LOOP, calibration_only=True):
    """The same ages, keyed by participant, so an outcome can be split by age.

    `ages` drops the identifier, which is all a cohort matcher needs and not enough for a
    subgroup analysis: without the key there is no way to ask what the trial's under-18s did
    as against its adults. This is the only demographic the release keeps, so it is the only
    subgroup that can be cut on the real side at all. The Commons carries no age, and the
    CLOSE-IT reference is a stand-in whose ages are drawn uniformly across the eligibility
    range, so neither supports this.
    """
    import pandas as pd

    d = pd.read_csv(_path("DiabScreening_a.txt"), sep="|", encoding="utf-16")
    keep = set(roster().query(f"trtGroup == '{arm}'").PtID)
    if calibration_only:
        keep &= set(split()["calibration"])
    d = d.loc[d.PtID.isin(keep), ["PtID", "AgeAtEnrollment"]].copy()
    d["AgeAtEnrollment"] = pd.to_numeric(d["AgeAtEnrollment"], errors="coerce")
    d = d.dropna(subset=["AgeAtEnrollment"])
    return {int(p): float(a) for p, a in zip(d.PtID, d.AgeAtEnrollment)}


def therapy_settings(arm=CLOSED_LOOP, calibration_only=True):
    """Each participant's prescribed basal profile, carbohydrate ratio and correction factor.

    Returns half-hourly arrays, so hour `h` is index `2 * h`. The basal columns are sparse
    because sites recorded a rate only where it changed, so they are carried forward. The
    bolus settings arrive as up to ten start and end times with a ratio and a factor each,
    and are expanded onto the same grid, wrapping past midnight.

    The first record carrying a basal profile is used, which is the profile the participant
    entered the trial on rather than whatever it was later adjusted to.
    """
    import pandas as pd

    d = pd.read_csv(_path("InsulinPumpSettings_a.txt"), sep="|", encoding="utf-16")
    keep = set(roster().query(f"trtGroup == '{arm}'").PtID)
    if calibration_only:
        keep &= set(split()["calibration"])
    d = d[d.PtID.isin(keep)]

    out = {}
    for pt, g in d.groupby("PtID"):
        g = g.sort_values("RecID")
        row = g[g[HALF_HOURLY_BASAL].notna().any(axis=1)].head(1)
        if row.empty:
            continue
        basal = pd.to_numeric(row[HALF_HOURLY_BASAL].iloc[0],
                              errors="coerce").ffill().bfill().to_numpy(float)
        if not np.isfinite(basal).all() or basal.sum() <= 0:
            continue
        cr, cf = np.full(48, np.nan), np.full(48, np.nan)
        for k in range(1, 11):
            cols = (f"InsBolusStart{k}Hr", f"InsBolusStart{k}Min",
                    f"InsBolusEnd{k}Hr", f"InsBolusEnd{k}Min", f"CHORatio{k}", f"CorrFactor{k}")
            if any(c not in row for c in cols):
                continue
            sh, sm, eh, em, ratio, factor = (row[c].iloc[0] for c in cols)
            if any(v != v for v in (sh, sm, eh, em, ratio, factor)):
                continue
            s, e = int(sh) * 2 + (sm >= 30), int(eh) * 2 + (em >= 30)
            span = range(s, e) if e > s else [*range(s, 48), *range(0, max(e, 1))]
            for i in span:
                cr[i % 48], cf[i % 48] = ratio, factor
        tdd = row.CurrTotInsDaily.iloc[0]
        out[int(pt)] = {"basal": basal, "carb_ratio": cr, "correction_factor": cf,
                        "total_daily_insulin": float(tdd) if tdd == tdd else float("nan")}
    return out

# Level 4's known answer, no longer taken from the literature. DCLP3 randomised it, so this
# is the effect measured on the people it was measured on. Those fields are real and the
# rebuild does not move them.
#
# `timsim_measured` and `timsim_interval` are a different kind of thing and were sitting here
# unmarked: they are this package's own reproduction of that effect, frozen as constants on
# 8 August 2026, on the hundred-subject population, before the gain refit and the reseeding.
# A rerun of the validation suite does not correct them, because nothing recomputes them. They
# also cannot be reproduced by the procedure the documentation describes, which compares the
# `loop` layer on and off, and `loop` has since stopped being a layer at all. Remeasuring means
# choosing a controller pair rather than a layer, which is a decision rather than a rerun, so
# they are marked stale here rather than quietly refreshed.
KNOWN_ANSWER = {
    "outcome": "time in range, percentage points",
    "closed_loop_median": 69.7, "pump_median": 55.7,
    "difference": 13.9, "mann_whitney_p": 6.2e-05,
    "trial_reported": 11.0,
    "timsim_measured": 12.9, "timsim_interval": (8.2, 15.4),
    "timsim_measured_on": "2026-08-08, population of 100, before the gain refit and reseeding",
    "timsim_is_stale": True,
    "note": "calibration half only; the trial's own headline figures are 71% against 59%",
}

# Eight of the ten statistics that can be read off a glucose trace land inside
# `analysis.signatures.REAL_RANGE`, which was built from four cohort medians on different
# users and devices. That is a substantial independent validation of a reference this
# package has leaned on throughout.
#
# One disagrees materially. Hypoglycaemia rebound reads 45.97, inter-quartile range 38.3 to
# 53.2, against a range of 23.2 to 28.4. It reads 41.4 off the Clarity export too, so it is
# not a smoothing artefact. Real closed-loop users rebound above 180 after a low far more
# often than the four-cohort reference says, which means roughly half of the gap this
# package has been trying to close on that row was the reference rather than the simulator.
#
# Hypoglycaemia recovery reads 47.5 against 50 to 59, marginally faster than the range, with
# an inter-quartile range that overlaps it.
DISAGREEMENTS = ("hypo_reb",)
MARGINAL = ("hypo_rec", "acf30")


def main():
    if not available():
        raise SystemExit(f"DCLP3 not found at {DCLP3_DIR}; set DCLP3_DIR")
    if not os.path.exists(cache_path(DEFAULT_SOURCE)):
        build_cache()
    s = split()
    print(json.dumps({k: v for k, v in s.items() if k != "held_out"}, indent=1))
    print(f"held-out participants sealed behind fingerprint {s['fingerprint']}")


if __name__ == "__main__":
    main()


__all__ = ["available", "roster", "build_cache", "load", "traces", "split",
           "signatures", "arm_outcomes", "CLOSED_LOOP", "PUMP", "DCLP3_DIR"]
