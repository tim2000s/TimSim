"""Every measurement on disk says which experiment produced it.

Three defects in one rebuild came from the same absence. The ladder reused twenty rungs measured
the previous day because nothing recorded which population they belonged to. The arbiter read six
configurations against each other that had been measured before the population was regenerated.
Neither was detectable from the files themselves, and both produced complete, plausible output.

A stamp does not prevent staleness on its own, since something has to check it. What it does is
make the check possible, so these tests assert that the stamp exists and that the field which
identifies the patient model is populated rather than a placeholder.

The tests read what is on disk rather than running anything, so they pass vacuously on a clean
checkout with no measurements and become meaningful once a rebuild has run.
"""
import glob
import json
import os

import pytest

from timsim import provenance

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

# Outputs computed from real records alone. They carry no population and are deliberately kept
# across a rebuild rather than regenerated, so a population stamp on them would be a fiction.
# `commons_requirement` is the reconstructed daily insulin the Commons cohort is matched on, and
# `real_meals` is the uncovered-meal reference; both are excluded from the archive step for the
# same reason.
REAL_DATA_ONLY = {"real_meals.json", "real_meals_dia.json", "commons_requirement.json",
                  "commons_cohort.json", "cohorts.json"}

# Written before this test existed and not yet regenerated. Each entry is a measurement whose
# producer now stamps but whose file predates the change, so it clears on the next rebuild.
# Anything added here needs a reason and a rebuild to remove it.
#
# The list asserted that of every entry once when it was true of only nine. Five producers,
# `fit_control_iq`, `capability_decomposition`, `calibrate_exercise`, `calibrate_glucagon` and
# `calibrate_egp_floor`, wrote no stamp at all, so their entries described a wait that would
# never end and `control_iq_fit.json` sat unguarded on disk while the bench read it. All five
# stamp now, which is what makes the sentence above true. Checking a suppression list against
# the code it excuses is the only way that kind of entry surfaces.
PENDING_REBUILD = {"bench_matrix.json", "control_iq_fit.json",
                   "meal_response.json", "two_benches.json", "oref_autosens_on.json",
                   "oref_autosens_off.json", "capability_decomposition.json",
                   "hypoglycaemia_arms.json", "rescue_bio_alone.json",
                   "exercise_arm.json", "exercise_calibration.json",
                   "glucagon_calibration.json", "egp_floor.json"}


def _measurements():
    for path in sorted(glob.glob(os.path.join(MEASUREMENTS, "*.json"))):
        name = os.path.basename(path)
        if name in REAL_DATA_ONLY or name in PENDING_REBUILD:
            continue
        yield path, name


def _stamp(path):
    try:
        payload = json.load(open(path))
    except (ValueError, OSError):
        return None
    return payload.get("provenance") if isinstance(payload, dict) else None


@pytest.mark.parametrize("path,name", list(_measurements()))
def test_measurement_carries_a_provenance_stamp(path, name):
    """A file with no stamp cannot be shown to belong to the run that is being reported."""
    assert _stamp(path) is not None, (
        f"{name} carries no provenance stamp, so nothing can establish which population, "
        f"settings or commit produced it. Either stamp its producer or add it to "
        f"REAL_DATA_ONLY with a reason.")


@pytest.mark.parametrize("path,name", list(_measurements()))
def test_binding_fields_are_populated(path, name):
    """A binding field carrying a placeholder is worse than one that is absent.

    `simglucose` read `__version__`, which the package does not define, so every run recorded
    the string "unknown". Two results computed under different versions of the patient model
    then compared as compatible, because both claimed ignorance in identical words. A field
    that cannot distinguish anything should not be in `BINDING`.
    """
    stamp = _stamp(path)
    if stamp is None:
        pytest.skip("covered by the test above")
    for field in provenance.BINDING:
        value = stamp.get(field)
        assert value is not None, f"{name}: binding field {field} is absent"
        assert value != "unknown", (
            f"{name}: binding field {field} is the placeholder 'unknown', which makes two "
            f"different experiments compare as the same one")


def test_the_simglucose_version_resolves():
    """The patient model's version is readable, since the whole model depends on it."""
    version = provenance.stamp()["simglucose"]
    assert version and version != "unknown", (
        "simglucose's version could not be determined, so no result can be bound to the "
        "patient model that produced it")
    assert version[0].isdigit(), version


def test_ladder_rungs_are_stamped_if_present():
    """The rungs are the case that failed, so they are asserted directly."""
    rungs = glob.glob(os.path.join(REPO, "docs", "ladder", "*.json"))
    if not rungs:
        pytest.skip("no ladder rungs on disk")
    unstamped = [os.path.basename(p) for p in rungs
                 if json.load(open(p)).get("provenance") is None]
    assert not unstamped, f"unstamped ladder rungs would be silently reused: {unstamped}"
