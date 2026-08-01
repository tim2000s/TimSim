"""How closely does the full stack match real data? Prints the verdict table."""
from timsim import signatures, simulate_cohort
from timsim.population import names

results = simulate_cohort(names("adult"), days=28, progress=True)
stats = signatures.evaluate(results)
print()
print(signatures.report(stats))

n_in = sum(signatures.in_real_range(k, v[0]) for k, v in stats.items()
           if k in signatures.REAL_RANGE)
print(f"\n{n_in} of {len(signatures.REAL_RANGE)} signatures inside the real range")
completed = sum(r.completed for r in results)
print(f"{completed} of {len(results)} subjects completed the run")
