"""What each layer does, one at a time.

Adds one mechanism per row so that a movement is attributable to a named cause rather
than to the bundle. This is the same measurement that produced the table in
docs/FIDELITY.md, at smaller scale so it runs in a few minutes.
"""
from simperson import signatures, simulate_cohort
from simperson.population import names

LADDER = [
    ("stock 2008", ()),
    ("+physiology", ("physiology",)),
    ("+behaviour", ("physiology", "behaviour")),
    ("+loop", ("physiology", "behaviour", "loop")),
    ("+sensor", ("physiology", "behaviour", "loop", "sensor")),
]
SUBJECTS = names("adult")[:10]
KEYS = ["cv", "tail", "acf30", "acf60", "outcome", "hypo_rec", "hypo_reb",
        "compress", "noise", "drift"]

print(f"{'layer':<14}" + "".join(f"{k:>9}" for k in KEYS))
for label, layers in LADDER:
    results = simulate_cohort(SUBJECTS, days=14, layers=layers, progress=False)
    stats = signatures.evaluate(results)
    print(f"{label:<14}" + "".join(f"{stats[k][0]:9.2f}" for k in KEYS))

print("\nreal range")
print(f"{'':<14}" + "".join(f"{signatures.REAL_RANGE[k][0]:4.1f}-{signatures.REAL_RANGE[k][1]:<4.1f}"
                            for k in KEYS))
