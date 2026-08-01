"""One subject, four weeks, everything switched on."""
from timsim import simulate

r = simulate("adult#001", days=28, seed=1)
s = r.summary()
print(f"{s['name']}: mean {s['mean']:.0f} mg/dL, CV {s['cv']:.1f}%, "
      f"TIR {s['tir']:.1f}%, TBR {s['tbr']:.1f}%")
print(f"insulin {s['insulin_per_day']:.1f} U/day, {s['rescues']} rescues, "
      f"{s['unannounced_meals']} unannounced meals, ISF drift {s['isf_weekly_cv']:.1f}%")
print("completed the run" if s["completed"] else "DID NOT COMPLETE")
