"""Glucose production and remote insulin at a spontaneous low, against a clamp plateau.

`examples/hypoglycaemic_clamp.py` measures production at the protocol the human references were
measured at. This measures the same quantity where it would be read if a clamp were not run, at
lows the algorithm arrived at on its own, and the two disagree by roughly a factor of nine.

The reason is the insulin. Production is `kp1 - kp2*Gp - kp3*Id`, and a spontaneous low is
reached by a loop withholding insulin while a clamp is conducted with insulin held high, so
`Id` at a spontaneous low sits nearer its euglycaemic value than its clamped one. Neither
measurement is wrong about the model; only one of them is comparable with a published figure.

    python examples/production_during_a_low.py
"""
import json
import os
import numpy as np
from concurrent.futures import ProcessPoolExecutor

from timsim import provenance, seeds

# Printed to stdout and wrote nothing, so its figures were quoted in four documents from a log
# that the next rebuild overwrote.
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "docs", "measurements", "production_low.json")

SUBJECTS = [f"adult#{i:03d}" for i in range(1, 21)]

DAYS, SEED = 28, seeds.BENCH
LAYERS = ("physiology", "behaviour", "sensor", "site")
LOW = 54.0                    # mg/dL, the threshold a low is counted below
EUGLYCAEMIC = (90.0, 130.0)   # mg/dL, the band the comparison is made against


def one(name):
    """One subject, tracing production and remote insulin at every step of a run.

    The patient is traced rather than the result, because `Result` carries glucose and
    delivery and neither of the two state variables production depends on.
    """
    from timsim.patient import varying as V
    from timsim.simulation.run import simulate
    seen = []
    base_step = V.VaryingPatient.step

    def traced(self, action, *a, **kw):
        q = self._params
        seen.append((float(self.observation.Gsub), float(self.state[8]),
                     float(max(q.kp1 - q.kp2 * self.state[3] - q.kp3 * self.state[8], 0.0))))
        return base_step(self, action, *a, **kw)

    # Titrated settings, so the lows this reads production during are the lows the person
    # would actually have. The insulin state during a low is what makes the figure
    # interpretable, and untitrated settings roughly double how often lows happen.
    from timsim.therapy import titrate
    prof = titrate.profile_for(name)
    V.VaryingPatient.step = traced
    try:
        simulate(name, days=DAYS, seed=SEED, layers=LAYERS, controller="trend",
                 profile=prof, hypo_egp_defence=0.0, hypo_defence_gain=0.0)
    except Exception:
        pass                  # a run that terminates early still contributes what it reached
    finally:
        V.VaryingPatient.step = base_step

    a = np.asarray(seen, dtype=float)
    if not len(a):
        return None
    low = a[a[:, 0] < LOW]
    eu = a[(a[:, 0] > EUGLYCAEMIC[0]) & (a[:, 0] < EUGLYCAEMIC[1])]
    if not len(low) or not len(eu):
        return None
    return {"name": name, "n_low": int(len(low)),
            "id_low": float(np.median(low[:, 1])), "egp_low": float(np.median(low[:, 2])),
            "id_eu": float(np.median(eu[:, 1])), "egp_eu": float(np.median(eu[:, 2]))}


def main(workers=7):
    with ProcessPoolExecutor(max_workers=workers) as ex:
        rows = [r for r in ex.map(one, SUBJECTS) if r]
    print(f"{len(rows)} of {len(SUBJECTS)} subjects reached below {LOW:.0f} mg/dL")
    a = np.asarray([[r["id_low"], r["id_eu"], r["egp_low"], r["egp_eu"]] for r in rows])
    keys = ("id_low", "id_eu", "egp_low", "egp_eu")
    summary = {}
    for i, label in ((0, f"remote insulin below {LOW:.0f}"), (1, "remote insulin at 90 to 130"),
                     (2, f"production below {LOW:.0f}"), (3, "production at 90 to 130")):
        summary[keys[i]] = {"label": label, "median": float(np.median(a[:, i])),
                            "p10": float(np.percentile(a[:, i], 10)),
                            "p90": float(np.percentile(a[:, i], 90))}
        print(f"  {label:>28}  median {np.median(a[:, i]):7.2f}  "
              f"p10 {np.percentile(a[:, i], 10):7.2f}  p90 {np.percentile(a[:, i], 90):7.2f}")
    # The clamp figures were printed here as constants and went stale: the line read 0.14
    # mg/kg/min at the 55 mg/dL plateau long after the refit put the undefended model at 0.49,
    # inside the human band. They are read from the clamp's own output now, or omitted.
    try:
        clamp = json.load(open(os.path.join(os.path.dirname(OUT), "clamp.json")))
        step = next(s for a_ in clamp["arms"] if a_["hepatic_defence"] == 0.0
                    for s in a_["steps"] if s["target"] == 55)
        print(f"\n  the clamp holds remote insulin at {step['id_median']:.0f} at its 55 mg/dL "
              f"plateau, where production reads {step['egp_median']:.2f} mg/kg/min; the human "
              f"reference at that plateau is 0.42 to 0.84")
    except (OSError, ValueError, KeyError, StopIteration):
        print("\n  clamp.json is not on disk, so the plateau comparison is omitted rather than "
              "quoted from a constant")
    json.dump({"subjects": SUBJECTS, "low_threshold": LOW, "n_reaching_low": len(rows),
               "n_subjects": len(SUBJECTS), "provenance": provenance.stamp(),
               "summary": summary, "runs": rows}, open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
