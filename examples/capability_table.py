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
import numpy as np
from concurrent.futures import ProcessPoolExecutor

from timsim.analysis import signatures

SUBJECTS = [f"adult#{i:03d}" for i in range(1, 21)]
DRIVERS = ["basal-bolus", "trend", "boost", "oref"]
LAYERS = ("physiology", "behaviour", "sensor", "site")
DAYS, SEED = 28, 11


def driver_for(name, d):
    if d == "boost":
        from timsim.controller import boost_bridge
        return boost_bridge.BoostBridgeController(name)
    if d == "oref":
        from timsim.controller import oref
        return oref.OrefController(name)
    return d


def one(job):
    from timsim.simulation.run import simulate
    name, d = job
    ctrl = driver_for(name, d)
    try:
        r = simulate(name, days=DAYS, seed=SEED, layers=LAYERS, controller=ctrl)
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
    for k, label, _ in signatures.SIGS:
        a = np.asarray([r["values"][k] for r in ok if k in r.get("values", {})], dtype=float)
        a = a[np.isfinite(a)]
        if not len(a):
            continue
        b = signatures.REAL_RANGE.get(k)
        ref = f"{b[0]:g} to {b[1]:g}" if b else ""
        print(f"| {label:<38} | {np.percentile(a, 10):.2f} | {np.median(a):.2f} | "
              f"{np.percentile(a, 90):.2f} | {ref} |")


if __name__ == "__main__":
    main()
