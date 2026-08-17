"""What each layer does, one at a time.

Adds one mechanism per column so that a movement is attributable to a named cause rather
than to the bundle. This is what produced the table in docs/FIDELITY.md.

Two of its choices are superseded by `layer_ladder_by_controller.py`, and a reader comparing
the two tables should know which. This one changes the driving algorithm at the `+loop`
column, so the columns to its right are measured under a different driver from those to its
left; the other holds the driver constant and walks the ladder once per driver. And this one
adds physiology before behaviour, which adds a mechanism before its antidote and loses half
the cohort at that rung, so the columns above it are measured on fewer and different people.

Each arm is independent, so with `--arm` you can run them in parallel processes and then
`--table` to collect. Running all six in one process takes roughly an hour and a quarter for ten
subjects over 28 days.

    python examples/layer_ablation.py                 # all six, serially
    python examples/layer_ablation.py --arm behaviour # one arm, writes docs/behav.json
    python examples/layer_ablation.py --table         # collect and print
"""
import argparse, json, os

from timsim import signatures, simulate_cohort
from timsim import seeds
from timsim.population import names

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "docs")

# One mechanism per column, cumulative left to right. The `+loop` column adds no layer:
# it switches the driving controller from open-loop basal-bolus to the reference
# correction loop, which is a change to what is dosing rather than to the person.
#
# One mechanism per column, cumulative left to right. The default simulator is the `all`
# column, every layer including the infusion site. The `sens` column beside it is the same
# thing without that layer, kept because it scores three signatures better and is the
# configuration a classifier finds easier to tell from real data. That trade is the thing
# worth watching whenever anything here changes.
#
# The S2013 risk term is not a column at all, for the same reason it is switched off:
# `--arm hypo` runs it as a branch off the physiology arm for anyone remeasuring its cost.
ARMS = [
    ("stock", "stock 2008", (), {"controller": "basal-bolus"}),
    ("phys", "+physiology", ("physiology",), {"controller": "basal-bolus"}),
    ("behav", "+behaviour", ("physiology", "behaviour"), {"controller": "basal-bolus"}),
    ("loop", "+loop", ("physiology", "behaviour"), {"controller": "reference"}),
    ("sens", "+sensor", ("physiology", "behaviour", "sensor"), {"controller": "reference"}),
    ("all", "+site", ("physiology", "behaviour", "sensor", "site"),
     {"controller": "reference"}),
]

# Off the cumulative path: the physiology arm with S2013's risk term switched on.
BRANCHES = {
    "hypo": ("+S2013 hypo", ("physiology",), {"hypo_risk_gain": 0.05}),
    # Visentin's per-subject seven-class diurnal sensitivity in place of the common
    # cosine, run on the default stack so its effect is readable against the `sens` column.
    "visentin": ("+Visentin S_I", ("physiology", "behaviour", "sensor"),
                 {"si_pattern": "visentin"}),
    # The same, with this package's day-to-day term switched off, because Visentin's model
    # carries its own and running both compounds them.
    "visentin1": ("+Visentin S_I alone", ("physiology", "behaviour", "sensor"),
                  {"si_pattern": "visentin", "si_interday_cv": 0.0}),
}
KEYS = ["cv", "tail", "acf30", "acf60", "outcome", "diurnal", "hypo_rec", "hypo_reb",
        "compress", "noise", "drift"]
LABELS = {
    "cv": "Glucose variability (CV%)", "tail": "Rise tail P(dBG>10/5min) %",
    "acf30": "Autocorrelation @30min", "acf60": "Autocorrelation @60min",
    "outcome": "Outcome SD @stuck-high (mg/dL)", "diurnal": "Diurnal amplitude (mg/dL)",
    "hypo_rec": "Hypo recovery to 100 (min)", "hypo_reb": "Hypo rebound >180 %",
    "compress": "Compression lows /30d", "noise": "Sensor jitter (mg/dL)",
    "drift": "ISF drift (weekly %CV)",
}


def run_arm(key, layers, subjects, days, kwargs=None):
    # Titrated settings, as every benchmark uses; the physiological fallback describes a
    # person no titration would leave in place.
    from timsim.therapy import titrate
    results = simulate_cohort(subjects, days=days, seed=seeds.BENCH, layers=layers,
                              profile_factory=titrate.profile_for,
                              progress=False, **(kwargs or {}))
    stats = signatures.evaluate(results)
    payload = {"label": key, "layers": list(layers), "seed": seeds.BENCH, "days": days,
               "stats": {k: list(v) for k, v in stats.items()},
               "completed": int(sum(r.completed for r in results)),
               "n": len(results),
               "tbr": [round(r.time_below_70, 1) for r in results]}
    os.makedirs(OUT, exist_ok=True)
    json.dump(payload, open(os.path.join(OUT, f"{key}.json"), "w"), indent=1)
    return payload


def table():
    data = {k: json.load(open(os.path.join(OUT, f"{k}.json"))) for k, _, _, _ in ARMS}
    heads = [h for _, h, _, _ in ARMS]
    print("| Signature | Real range | " + " | ".join(heads) + " | In range |")
    print("|---" * (len(heads) + 3) + "|")
    n_in = n_base = n_site = 0
    for key in KEYS:
        lo, hi = signatures.REAL_RANGE[key]
        dp = 2 if key.startswith("acf") else 1
        cells = [f"{data[k]['stats'][key][0]:.{dp}f}" for k, _, _, _ in ARMS]
        ok = signatures.in_real_range(key, data["all"]["stats"][key][0])
        n_in += ok
        n_site += signatures.in_real_range(key, data["sens"]["stats"][key][0])
        n_base += signatures.in_real_range(key, data["stock"]["stats"][key][0])
        print(f"| {LABELS[key]} | {lo:.{dp}f}-{hi:.{dp}f} | " + " | ".join(cells)
              + f" | {'yes' if ok else 'no'} |")
    print(f"\n{n_base} of {len(KEYS)} for the stock personae, "
          f"{n_site} of {len(KEYS)} with four layers, "
          f"{n_in} of {len(KEYS)} with all five, which is the default.")
    print("The 'In range' column is the default arm. It allows the 10% padding "
          "`signatures.in_real_range`\napplies, and it is the weaker of the two tests "
          "this package runs: `examples/configuration_arbiter.py`\nasks whether a day of "
          "this looks like a day of real data, and prefers the five-layer arm.")
    for k, h, _, _ in ARMS:
        d = data[k]
        print(f"{h:>14}: completed {d['completed']}/{d['n']}, "
              f"time below 70 {min(d['tbr']):.1f}-{max(d['tbr']):.1f}%")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arm", choices=[k for k, _, _, _ in ARMS] + list(BRANCHES))
    ap.add_argument("--table", action="store_true")
    ap.add_argument("--subjects", type=int, default=10)
    ap.add_argument("--days", type=int, default=28)
    a = ap.parse_args()

    if a.table:
        return table()
    subjects = names("adult")[:a.subjects]
    arms = ([(a.arm, *BRANCHES[a.arm])] if a.arm in BRANCHES
            else [x for x in ARMS if a.arm is None or x[0] == a.arm])
    for key, label, layers, kwargs in arms:
        print(f"running {label} ...", flush=True)
        run_arm(key, layers, subjects, a.days, kwargs)
    if a.arm is None:
        print()
        table()


if __name__ == "__main__":
    main()
