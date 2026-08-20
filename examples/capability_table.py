"""The simulated column of the capability table, on the shipped configuration.

Twenty subjects under each of the four drivers with the full stack and no overrides, which is
what that column is meant to describe. Running it with a layer or a mechanism switched off
produces a table describing a configuration the package does not ship, and the difference is
large enough to change how many signatures land inside the reference: with the hepatic defence
off, nine of ten simulated medians sit inside the range of real individuals rather than ten.

The real columns come from the OpenAPS Data Commons export and are computed elsewhere, so this
prints the simulated percentiles and the completion count and leaves the comparison to
`docs/CAPABILITY.md`. Completion matters to the reading: the runs that fail are the ones that
went lowest, so every percentile here is conditioned on survival.

    python examples/capability_table.py
"""
import json
import os
import numpy as np
from concurrent.futures import ProcessPoolExecutor

from timsim.analysis import signatures

SUBJECTS = [f"adult#{i:03d}" for i in range(1, 21)]
DRIVERS = ["basal-bolus", "trend", "boost", "oref"]
LAYERS = ("physiology", "behaviour", "sensor", "site")
from timsim import provenance, seeds

DAYS, SEED = 28, seeds.BENCH

# This printed a table and wrote nothing, so the headline capability figure existed only in a
# log that the next rebuild overwrote. A documentation audit on 20 August 2026 could not verify
# any of it, and the log is neither stamped nor archived. It writes a stamped file now.
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "docs", "measurements", "capability_table.json")


def driver_for(name, d, prof):
    if d == "boost":
        from timsim.controller import boost_bridge
        return boost_bridge.BoostBridgeController(name, profile=prof)
    if d == "oref":
        from timsim.controller import oref
        return oref.OrefController(name, profile=prof)
    return d


def one(job):
    from timsim.simulation.run import simulate
    from timsim.therapy import titrate
    name, d = job
    # Titrated settings, as every other measurement uses. Passing no profile fell back to
    # the physiological ones, which no real person carries: the median physiological
    # correction factor is well under half the recorded DCLP3 value, and handing oref0 SMB
    # the physiological figure doubles its time below 70 mg/dL. Three of the ten signatures
    # read hypoglycaemia behaviour, so the table was partly describing the settings.
    prof = titrate.profile_for(name)
    ctrl = driver_for(name, d, prof)
    try:
        r = simulate(name, days=DAYS, seed=SEED, layers=LAYERS, controller=ctrl,
                     profile=prof)
    except Exception as e:
        return {"name": name, "driver": d, "completed": False, "error": str(e)[:120]}
    finally:
        if hasattr(ctrl, "close"):
            ctrl.close()
    packed = signatures.from_result(r)
    return {"name": name, "driver": d, "completed": bool(r.completed),
            "values": {k: float(fn(packed)) for k, _, fn in signatures.SIGS}}


def main(workers=6):
    jobs = [(n, d) for d in DRIVERS for n in SUBJECTS]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        rows = list(ex.map(one, jobs))
    ok = [r for r in rows if r.get("completed")]
    print(f"{len(ok)} of {len(rows)} runs completed")
    for d in DRIVERS:
        sub = [r for r in rows if r["driver"] == d]
        print(f"  {d:>12} {sum(r.get('completed', False) for r in sub)}/{len(sub)}")

    print(f"\n| {'Signature':<38} | p10 | median | p90 | reference |")
    print("|---|---|---|---|---|")
    summary = {}
    for k, label, _ in signatures.SIGS:
        a = np.asarray([r["values"][k] for r in ok if k in r.get("values", {})], dtype=float)
        a = a[np.isfinite(a)]
        if not len(a):
            continue
        b = signatures.REAL_RANGE.get(k)
        ref = f"{b[0]:g} to {b[1]:g}" if b else ""
        summary[k] = {"label": label, "n": int(len(a)),
                      "p10": float(np.percentile(a, 10)), "median": float(np.median(a)),
                      "p90": float(np.percentile(a, 90)),
                      "real_range": list(b) if b else None,
                      "in_real_range": bool(signatures.in_real_range(k, float(np.median(a))))
                      if b else None}
        print(f"| {label:<38} | {np.percentile(a, 10):.2f} | {np.median(a):.2f} | "
              f"{np.percentile(a, 90):.2f} | {ref} |")

    inside = sum(1 for v in summary.values() if v["in_real_range"])
    scored = sum(1 for v in summary.values() if v["in_real_range"] is not None)
    print(f"\n{inside} of {scored} simulated medians inside the real range")
    json.dump({"subjects": SUBJECTS, "drivers": DRIVERS, "layers": list(LAYERS),
               "days": DAYS, "seed": SEED, "provenance": provenance.stamp(),
               "completed": len(ok), "n_runs": len(rows),
               "inside_real_range": inside, "scored": scored,
               "summary": summary, "runs": rows},
              open(OUT, "w"), indent=1)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
