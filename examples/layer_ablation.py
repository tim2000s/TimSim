"""What each layer does, one at a time.

Adds one mechanism per column so that a movement is attributable to a named cause rather
than to the bundle. This is what produced the table in docs/FIDELITY.md.

Each arm is independent, so with `--arm` you can run them in parallel processes and then
`--table` to collect. Running all six in one process takes roughly an hour and a quarter for ten
subjects over 28 days.

    python examples/layer_ablation.py                 # all six, serially
    python examples/layer_ablation.py --arm behaviour # one arm, writes docs/behav.json
    python examples/layer_ablation.py --table         # collect and print
"""
import argparse, json, os

from timsim import signatures, simulate_cohort
from timsim.population import names

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "docs")

# One mechanism per column, cumulative left to right. The default simulator is the `sens`
# column, which is what `DEFAULT_LAYERS` runs and what every other number in `docs/` was
# measured against. The `all` column adds the infusion site layer, which is off by default
# and kept here because the size of what it trades is the thing worth watching.
#
# The S2013 risk term is not a column at all, for the same reason it is switched off:
# `--arm hypo` runs it as a branch off the physiology arm for anyone remeasuring its cost.
ARMS = [
    ("stock", "stock 2008", (), {}),
    ("phys", "+physiology", ("physiology",), {}),
    ("behav", "+behaviour", ("physiology", "behaviour"), {}),
    ("loop", "+loop", ("physiology", "behaviour", "loop"), {}),
    ("sens", "+sensor", ("physiology", "behaviour", "loop", "sensor"), {}),
    ("all", "+site", ("physiology", "behaviour", "loop", "sensor", "site"), {}),
]

# Off the cumulative path: the physiology arm with S2013's risk term switched on.
BRANCHES = {
    "hypo": ("+S2013 hypo", ("physiology",), {"hypo_risk_gain": 0.05}),
    # Visentin's per-subject seven-class diurnal sensitivity in place of the common
    # cosine, run on the default stack so its effect is readable against the `sens` column.
    "visentin": ("+Visentin S_I", ("physiology", "behaviour", "loop", "sensor"),
                 {"si_pattern": "visentin"}),
    # The same, with this package's day-to-day term switched off, because Visentin's model
    # carries its own and running both compounds them.
    "visentin1": ("+Visentin S_I alone", ("physiology", "behaviour", "loop", "sensor"),
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
    results = simulate_cohort(subjects, days=days, layers=layers, progress=False,
                              **(kwargs or {}))
    stats = signatures.evaluate(results)
    payload = {"label": key, "layers": list(layers),
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
        ok = signatures.in_real_range(key, data["sens"]["stats"][key][0])
        n_in += ok
        n_site += signatures.in_real_range(key, data["all"]["stats"][key][0])
        n_base += signatures.in_real_range(key, data["stock"]["stats"][key][0])
        print(f"| {LABELS[key]} | {lo:.{dp}f}-{hi:.{dp}f} | " + " | ".join(cells)
              + f" | {'yes' if ok else 'no'} |")
    print(f"\n{n_base} of {len(KEYS)} for the stock personae, "
          f"{n_in} of {len(KEYS)} with the four default layers, "
          f"{n_site} of {len(KEYS)} with the site layer added.")
    print("The 'In range' column is the default arm, and allows the 10% padding "
          "`signatures.in_real_range` applies.")
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
