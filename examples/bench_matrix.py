"""Every simulated arm the validation paper needs, in one run.

The question each pairing answers is the same: holding one algorithm fixed, how far does the
simulated population sit from the real population running that algorithm, on the bare S2008
patient and on the layered bench? So the algorithm never varies inside a pairing and the
bench does.

    dclp3     control-iq   against the closed-loop arm of the DCLP3 trial
    dclp3     oref         the same cohort under a shipped algorithm
    commons   oref         against OpenAPS Data Commons users, who run this algorithm
    close_it  oref         against the CLOSE-IT trial, which randomised meal announcement

Announcement is a property of the person, so it only varies on the layered bench: the bare
patient has no behaviour layer and announces everything by construction. That gives four arms
per pairing rather than six.

Cohorts come from docs/measurements/cohorts.json and settings from the titration store, both
of which are stamped with the population they were built against, so a stale one raises
rather than quietly dosing a subject on another body's settings.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

import argparse
import json
import time
import numpy as np
from concurrent.futures import ProcessPoolExecutor

from timsim import provenance

from timsim import seeds

DAYS, SEED = 28, seeds.BENCH
LAYERS = ("physiology", "behaviour", "sensor", "site")
OUT = os.path.join(MEASUREMENTS, "bench_matrix.json")

PAIRINGS = [("dclp3", "control-iq"), ("dclp3", "oref"),
            ("commons", "oref"), ("close_it", "oref")]

# The validation set drops `dclp3 | oref`. That pairing exists in the matrix to compare two
# algorithms on one cohort, which is a different question; as a comparison against real people it
# has no reference, because DCLP3 participants ran Control-IQ and there is no published cohort of
# them running oref0. Each pairing here is a real population and the algorithm those people
# actually used.
VALIDATION_PAIRINGS = [("dclp3", "control-iq"), ("commons", "oref"), ("close_it", "oref")]
BENCHES = [("bare", (), "some", "titrated"),
           ("layered_always", LAYERS, "always", "titrated"),
           ("layered_some", LAYERS, "some", "titrated"),
           ("layered_never", LAYERS, "never", "titrated")]

# The same four arms as the matrix, run under one controller against every cohort rather than
# under each cohort's own algorithm. That measures the person rather than scoring an algorithm,
# and gives a fixed reference for reading a later comparison between controllers against.
#
# One bare arm, because the docstring above is right and was written on 15 August 2026: the bare
# patient has no behaviour layer and announces everything by construction. A version of this set
# carrying three bare arms was run on 20 August, produced three arms identical to every decimal
# of every measure, and spent a third of a 216-minute job establishing what the top of this file
# already said.
BASELINE_BENCHES = [("bare", (), "some", "titrated"),
                    ("layered_always", LAYERS, "always", "titrated"),
                    ("layered_some", LAYERS, "some", "titrated"),
                    ("layered_never", LAYERS, "never", "titrated")]

# The rungs, for asking how far each layer moves the outcomes towards the trial rather than what
# it does to a fidelity signature. `layer_ladder_by_controller.py` answers a different question,
# whether a layer moves a signature the same way under every driver, and it cannot answer this
# one: it records the twelve signatures and no outcome, and it runs on the first N adults rather
# than on a cohort matched to a trial, so no distance to a real population can be computed from
# it at all.
#
# Here the algorithm is held at whatever that trial's participants ran, the cohort is the one
# matched to them, and the layers accumulate. There is no loop rung, because the controller does
# not change up the ladder. `stock` and `site` are the same two arms the matrix calls `bare` and
# `layered_some`, kept so all five sit on one footing in one file.
LADDER_BENCHES = [("stock", (), "some", "titrated"),
                  ("phys", ("physiology",), "some", "titrated"),
                  ("behav", ("physiology", "behaviour"), "some", "titrated"),
                  ("sens", ("physiology", "behaviour", "sensor"), "some", "titrated"),
                  ("site", ("physiology", "behaviour", "sensor", "site"), "some", "titrated")]

# The validation set: what a user gets from stock S2008, what each layer changes on its own, and
# what all four change together, on cohorts matched to a real study.
#
# Two reference points rather than one, because an arm with no layers is not stock S2008. It still
# carries this package's titrated settings and its delivery limits, and both move outcomes as much
# as some layers do: handing oref0 the physiological correction factor instead of the titrated one
# doubles its time below 70 mg/dL. `stock` is dosed from the subject's own physiology, which is
# what simglucose gives you, and `base` is the same body on titrated settings. The difference
# between them is how much of this package's improvement is settings and delivery discipline
# rather than physiology and behaviour, and it is a result rather than an overhead.
#
# Each layer stands alone against `base`, so its effect is not entangled with the ones below it on
# a cumulative ladder.
#
# Meal announcement is carried only by the arms containing behaviour. `run.py` sets
# `announce="behaviour" in effective`, so an arm without it is told the exact carbohydrate of
# every meal and the announcement setting does nothing. Running the others at three settings
# produces three identical arms, which is issue 38.
_DEFAULT = ("physiology", "behaviour", "sensor", "site")
VALIDATION_BENCHES = [
    ("stock", (), "some", "physiological"),
    ("base", (), "some", "titrated"),
    ("physiology", ("physiology",), "some", "titrated"),
    ("behaviour", ("behaviour",), "some", "titrated"),
    ("sensor", ("sensor",), "some", "titrated"),
    ("site", ("site",), "some", "titrated"),
    ("all_layers", _DEFAULT, "some", "titrated"),
    ("behaviour_announced", ("behaviour",), "always", "titrated"),
    ("behaviour_unannounced", ("behaviour",), "never", "titrated"),
    ("all_layers_announced", _DEFAULT, "always", "titrated"),
    ("all_layers_unannounced", _DEFAULT, "never", "titrated"),
]


def one(job):
    cohort, controller, bench, name, layers, announcement, settings = job
    from timsim.simulation.run import simulate
    from timsim.therapy import profile as profile_mod, titrate
    arm = f"{cohort}|{controller}|{bench}"
    # How the subject is dosed travels in the job with everything else, so no start method can
    # strip it and no arm can be run on settings other than the ones it is labelled with.
    prof = (titrate.profile_for(name) if settings == "titrated"
            else profile_mod.for_subject(name))
    ctrl, t0 = controller, time.time()
    try:
        if controller == "oref":
            from timsim.controller import oref
            ctrl = oref.OrefController(name, profile=prof)
        r = simulate(name, days=DAYS, seed=SEED, layers=layers, controller=ctrl,
                     profile=prof, announcement=announcement)
    except Exception as exc:
        return {"arm": arm, "cohort": cohort, "controller": controller, "bench": bench,
                "settings": settings, "layers": list(layers), "announcement": announcement,
                "name": name, "completed": False, "error": str(exc)[:200],
                "seconds": time.time() - t0}
    finally:
        if hasattr(ctrl, "close"):
            ctrl.close()

    cgm = np.asarray(r.cgm, dtype=float)
    bg = np.asarray(r.bg, dtype=float)
    days = max(len(bg) * 5.0 / 1440.0, 1e-9)
    out = {"arm": arm, "cohort": cohort, "controller": controller, "bench": bench,
           "settings": settings, "layers": list(layers), "announcement": announcement,
           "name": name, "completed": bool(r.completed), "days": float(days),
           "seconds": time.time() - t0,
           "insulin_per_day": float(getattr(r, "insulin_units", float("nan")) / days),
           "rescue_per_30d": float(30.0 * getattr(r, "rescue_events", 0) / days),
           "final_bg": float(bg[-1]), "lowest_bg": float(np.min(bg)),
           "highest_bg": float(np.max(bg)),
           # Why a run ended, from `classify_termination`, rather than left to be reconstructed
           # from the final reading. It carries the direction, the day it stopped and whether an
           # infusion site failure was in progress, and every median above is conditioned on
           # survival, so the reasons belong beside the numbers rather than in a separate audit.
           "termination": getattr(r, "termination", None)}
    for sig, lab in ((cgm, "cgm"), (bg, "bg")):
        out[f"tir_{lab}"] = float(100.0 * np.mean((sig >= 70) & (sig <= 180)))
        out[f"tbr70_{lab}"] = float(100.0 * np.mean(sig < 70))
        out[f"tbr54_{lab}"] = float(100.0 * np.mean(sig < 54))
        out[f"tar180_{lab}"] = float(100.0 * np.mean(sig > 180))
        out[f"mean_{lab}"] = float(np.mean(sig))
        out[f"cv_{lab}"] = float(100.0 * np.std(sig, ddof=1) / np.mean(sig))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", default="1/1",
                    help="run one slice of the run list, as i/n. Slices are taken by "
                         "position after the list is built, so every machine builds the same "
                         "list from the same cohorts and takes a disjoint part of it.")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--controller",
                    help="run this one controller against every cohort instead of the recorded "
                         "pairings. The pairings exist because DCLP3 participants ran Control-IQ "
                         "and Commons users run oref0, so a pairing is like-for-like and this is "
                         "not. Use it to measure the person rather than to score an algorithm.")
    ap.add_argument("--benches", choices=("matrix", "baseline", "ladder", "validation"),
                    default="matrix",
                    help="'baseline' measures the bare arm at all three meal scenarios as well "
                         "as the layered arm; 'ladder' accumulates the layers one at a time so "
                         "each rung's distance to the trial can be read")
    a = ap.parse_args()
    # Named so nothing later can shadow them. They were `i` and `n`, and both were: the
    # progress loop rebound `i` to the completed-row count and the per-pairing print rebound
    # `n` to the last cohort's size, so the shard stamp recorded neither the index nor the
    # count. `merge_shards.py` reads that stamp to check it has every shard exactly once.
    shard_index, shard_count = (int(x) for x in a.shard.split("/"))

    from timsim.therapy import titrate
    rec = json.load(open(os.path.join(MEASUREMENTS, "cohorts.json")))
    current = titrate.population_fingerprint()
    if rec.get("population") and rec["population"] != current:
        raise SystemExit(f"cohorts.json was built against population {rec['population']} and "
                         f"the population on disk is {current}. Rerun build_cohorts.py.")
    titrated = set(titrate.titrated_subjects())

    benches = {"baseline": BASELINE_BENCHES, "ladder": LADDER_BENCHES,
               "validation": VALIDATION_BENCHES}.get(a.benches, BENCHES)
    default_pairings = VALIDATION_PAIRINGS if a.benches == "validation" else PAIRINGS
    pairings = ([(c, a.controller) for c in sorted(rec["cohorts"])] if a.controller
                else default_pairings)

    jobs = []
    for cohort, controller in pairings:
        subjects = [s for s in rec["cohorts"][cohort]["subjects"] if s in titrated]
        for bench, layers, announcement, settings in benches:
            jobs += [(cohort, controller, bench, n, layers, announcement, settings)
                     for n in subjects]
    total = len(jobs)
    if shard_count > 1:
        jobs = jobs[shard_index - 1::shard_count]
        print(f"shard {shard_index} of {shard_count}: {len(jobs)} of {total} runs", flush=True)
    print(f"{len(pairings)} pairings, {len(benches)} benches, {len(jobs)} runs", flush=True)
    for cohort, controller in pairings:
        n_titrated = len([s for s in rec["cohorts"][cohort]["subjects"] if s in titrated])
        print(f"  {cohort:9} {controller:11} {n_titrated} titrated subjects", flush=True)

    rows, t0 = [], time.time()
    with ProcessPoolExecutor(max_workers=int(os.environ.get("WORKERS", "10"))) as ex:
        for i, row in enumerate(ex.map(one, jobs), 1):
            rows.append(row)
            if i % 20 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)} done, {(time.time()-t0)/60:.1f} min", flush=True)
            if row.get("error"):
                print(f"  ! {row['arm']} {row['name']}: {row['error'][:110]}", flush=True)
    json.dump({"population": current, "days": DAYS, "seed": SEED,
               # Which arms and which cohort-controller pairs this file actually holds. A file
               # that records only its rows cannot be told apart from one run with different
               # options, which is how a cell labelled `bare` came to contain the layered arm.
               "bench_set": a.benches,
               "benches": [{"name": b, "layers": list(l), "announcement": ann,
                            "settings": st} for b, l, ann, st in benches],
               "pairings": [{"cohort": c, "controller": ctl} for c, ctl in pairings],
               "shard": {"index": shard_index, "of": shard_count,
                         "runs_in_shard": len(jobs), "runs_total": total},
               "provenance": provenance.stamp(), "runs": rows},
              open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out} after {(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    main()
