"""Drive your own algorithm, with the person layer still acting around it.

The controller sees only the announced carbohydrate, so unannounced meals arrive as an
unexplained rise, exactly as they do in practice. Rescue carbohydrate is never announced.
"""
from simglucose.controller.base import Action, Controller

from timsim import signatures, simulate_cohort
from timsim.population import names, params_for, therapy_for


class LowGlucoseSuspend(Controller):
    """Basal, suspended below 80 mg/dL. A deliberately crude baseline to compare against."""

    def __init__(self, name):
        p, q = params_for(name), therapy_for(name)
        self.basal = float(p["u2ss"]) * float(p["BW"]) / 6000.0
        self.cr = float(q["CR"])

    def policy(self, observation, reward, done, **info):
        meal = info.get("meal", 0.0) * info.get("sample_time", 3)
        bolus = meal / self.cr if meal > 0 else 0.0
        basal = 0.0 if observation.CGM < 80 else self.basal
        return Action(basal=basal, bolus=bolus / info.get("sample_time", 3))


subjects = names("adult")[:10]
results = simulate_cohort(subjects, days=14, controller_factory=LowGlucoseSuspend,
                          progress=False)
for r in results:
    s = r.summary()
    print(f"{s['name']:>16}  TIR {s['tir']:5.1f}%  TBR {s['tbr']:4.1f}%  CV {s['cv']:4.1f}%")
print()
print(signatures.report(signatures.evaluate(results)))
