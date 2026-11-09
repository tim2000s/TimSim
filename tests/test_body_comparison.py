"""A ranking on one body is compared with a ranking on the other only at the same code.

On 9 November 2026 the Hovorka ranking was set beside the S2008 one from 6 September, and four
hypoglycaemia pairs were reported as reversed by the body. Between the two commits lay the issue
54 fix, which alone moved oref0 SMB's time below 70 mg/dL by 2.16 points. ISSUES.md 55.
"""
import json
import os
import subprocess

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")
PAIRS = [("driver_ranking_s2008_current.json", "driver_ranking_hovorka.json")]
# Code that differs between the bodies by design, or cannot change a run.
BODY_ONLY = (":!timsim/patient/hovorka.py", ":!timsim/population/hovorka.py")


def code_differs(c1, c2):
    r = subprocess.run(["git", "-C", REPO, "diff", "--quiet", c1, c2, "--", "timsim",
                        "examples/rank_drivers.py", "examples/capability_table.py",
                        "examples/panel.py", *BODY_ONLY])
    if r.returncode not in (0, 1):
        pytest.skip(f"git cannot compare {c1[:7]} and {c2[:7]}")
    return r.returncode == 1


@pytest.mark.parametrize("first,second", PAIRS)
def test_compared_rankings_ran_on_the_same_code(first, second):
    paths = [os.path.join(MEASUREMENTS, f) for f in (first, second)]
    if not all(os.path.exists(p) for p in paths):
        pytest.skip("a ranking of the pair is not on disk")
    c1, c2 = (json.load(open(p))["provenance"]["commit"] for p in paths)
    assert not code_differs(c1, c2), (
        f"{first} ({c1[:7]}) and {second} ({c2[:7]}) ran on different simulation or driver "
        f"code, so a difference between them is not a difference between bodies")


def test_the_guard_fails_across_the_issue_54_fix():
    """The September S2008 ranking against the Hovorka one, the comparison that was made."""
    assert code_differs("a2d609c", "07fd086")
