"""How much of a measured meal rise is the sensor rather than the person.

Every real meal figure in this package is read off CGM, because that is all a real trace has.
Taking a maximum and a minimum off a noisy trace inflates the interval between them, so a rise
measured on CGM is larger than the rise the person had, and comparing it with a simulated rise
read off a clean trace is not like-for-like.

The same runs, the same meals and the same definition, scored on `Result.bg` and on `Result.cgm`.
The difference is the sensor and nothing else.

This exists because `liver_brake.json` and `liver_rebalance.json` compare a clean simulated rise
against a real one measured on CGM and therefore overstate the gap between them. Written after
Tim asked whether the candidate parameter set was sound, which it was not for that reason.

    python examples/rise_sensor_inflation.py
"""
import sys, os, json
sys.path.insert(0, "/Users/timstreet/StudioProjects/TimSim")
import multiprocessing as mp
import numpy as np
from timsim import seeds

def job(n):
    from timsim.simulation.run import simulate
    from timsim.analysis import meal_shape as ms
    r = simulate(n, days=21, seed=seeds.BENCH,
                 layers=("physiology", "behaviour", "sensor", "site"))
    if r.termination:
        return None
    mins = np.asarray(r.minutes, float)
    meals = [(float(m), float(g)) for m, g in r.meal_log]
    carbs = [m for m, _ in meals] + [float(x[1]) for x in r.rescue_log]
    out = {}
    for label, series in (("cgm", np.asarray(r.cgm, float)), ("bg", np.asarray(r.bg, float))):
        recs, _ = ms.shapes(meals, carbs, mins, series, window_min=240)
        v = [(x["peak_mgdl"] - x["trough_mgdl"]) / (x["grams"] / 10.0) for x in recs]
        t = [x["trough_to_peak_min"] for x in recs]
        out[label] = (float(np.median(v)), float(np.median(t)), len(v)) if len(v) >= 8 else None
    return out

if __name__ == "__main__":
    from examples.panel import dosable
    subs = dosable(20)
    with mp.Pool(7) as pool:
        rows = [r for r in pool.map(job, subs) if r and r["cgm"] and r["bg"]]
    c = np.array([r["cgm"][0] for r in rows]); b = np.array([r["bg"][0] for r in rows])
    ct = np.array([r["cgm"][1] for r in rows]); bt = np.array([r["bg"][1] for r in rows])
    print(f"n={len(rows)} subjects")
    print(f"  rise per 10 g on bg  {np.median(b):.1f}   on cgm {np.median(c):.1f}   "
          f"inflation {100*(np.median(c)/np.median(b)-1):+.0f} per cent")
    print(f"  trough to peak on bg {np.median(bt):.0f} min  on cgm {np.median(ct):.0f} min")
    from timsim import provenance
    json.dump({"provenance": provenance.stamp(), "n": len(rows), "bg_rise": float(np.median(b)), "cgm_rise": float(np.median(c)),
               "bg_ttp": float(np.median(bt)), "cgm_ttp": float(np.median(ct))},
              open("/Users/timstreet/StudioProjects/TimSim/docs/measurements/rise_sensor_inflation.json", "w"), indent=1)
