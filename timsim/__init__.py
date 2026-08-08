"""TimSim: a person-in-the-loop layer over the UVA/Padova virtual patient.

A physiological simulator describes a body. It does not describe someone eating without
telling the algorithm, drinking juice when the alarm goes off, or adjusting a setting
after a bad fortnight. Those behaviours dominate several of the statistics a real glucose
trace shows, and no amount of refinement to the differential equations produces them.

This package adds them, as separable layers over simglucose, together with a virtual
population large enough that a comparison is not at the mercy of one awkward subject.

    from timsim import simulate, signatures

    result = simulate("adult#001", days=28)
    print(result.summary())

The honest limits are in `docs/FIDELITY.md` and are worth reading before any result from
this package is used to argue for a change in treatment. `docs/OSAID.md` covers what is
needed on top of that before an automated insulin delivery system is judged here.
"""
__version__ = "0.2.0"

from .simulation.run import (DEFAULT_LAYERS, LAYERS, Result, simulate,
                             simulate_cohort)
from .analysis import safety, signatures
from . import population, therapy

__all__ = ["simulate", "simulate_cohort", "Result", "LAYERS", "DEFAULT_LAYERS",
           "signatures", "safety",
           "population", "therapy", "__version__"]
