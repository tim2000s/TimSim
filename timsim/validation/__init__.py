"""Graded checks on whether the simulator can be believed, and about what.

    checks        levels 1 to 6: consistency, face validity, fidelity, known answer,
                  discriminating power, robustness
    compare       putting a simulated cohort beside a real one without the usual mistake
    faults        level 7: what an algorithm does when its inputs go wrong
    ranking       whether the bench orders algorithms the way it should, checked against
                  algorithms broken on purpose
    replication   whether a classifier can tell simulated traces from real ones
    gate          pre-registered acceptance criteria and a pre-clinical verdict
    dclp3         the DCLP3 trial as a held-out, free-living, randomised reference
"""
from . import checks, compare, dclp3, faults, gate, ranking, replication
from .checks import minimum_detectable_difference

__all__ = ["checks", "compare", "dclp3", "faults", "gate", "ranking",
           "replication",
           "minimum_detectable_difference"]
