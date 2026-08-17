"""What produced a result, recorded with the result.

A figure from this package is only worth anything if it can be traced to the subjects and the
code that produced it. That mattered on one machine, where a population regenerated between two
measurements silently changed what every subject name referred to. It matters more across
machines, because a shard run on a laptop with a different population or an older commit merges
into the total without anything looking wrong: the arithmetic is fine, the runs completed, and
the answer is a mixture of two experiments.

So every result file carries a stamp, and anything combining results checks the stamps agree
before it combines them. The rule is that the population and the code must match exactly, and
everything else is recorded for the reader rather than enforced.
"""
import hashlib
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# What must agree before two sets of results describe the same experiment. Everything else in
# the stamp is context: useful when a result looks odd, not grounds for refusing to merge.
BINDING = ("population", "commit", "dirty")


def _git(*args):
    try:
        return subprocess.check_output(("git", "-C", REPO) + args,
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return None


# Results are written into the repository, so a run dirties the working tree by completing.
# Counting that as dirty would mark every result unreproducible and make the flag useless, so
# the question asked is narrower: did the code differ from the commit it claims to be.
NOT_CODE = ("docs/",)


def _dirty():
    """Whether anything outside the documentation and results differs from HEAD."""
    out = _git("status", "--porcelain")
    if out is None:
        return None
    # The porcelain prefix is two status characters, but the path follows after a variable
    # amount of space depending on whether the change is staged, so it is not a fixed slice.
    paths = [ln[2:].strip().split(" -> ")[-1].strip('"')
             for ln in out.splitlines() if ln.strip()]
    return bool([p for p in paths if not p.startswith(NOT_CODE)])


def _population():
    from .therapy import titrate
    return titrate.population_fingerprint()


def _settings_digest():
    """A digest of the titrated settings, which are as much an input as the population."""
    path = os.path.join(REPO, "timsim", "population", "params", "titrated_settings.json")
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:16]
    except OSError:
        return None


def stamp(**extra):
    """Everything needed to say whether two results belong to the same experiment."""
    out = {"population": _population(),
           "settings": _settings_digest(),
           "commit": _git("rev-parse", "HEAD"),
           "dirty": _dirty(),
           "host": platform.node(),
           "python": sys.version.split()[0],
           "platform": platform.platform(),
           "when": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        import simglucose
        out["simglucose"] = getattr(simglucose, "__version__", "unknown")
    except Exception:
        out["simglucose"] = None
    out.update(extra)
    return out


def describe(s):
    return (f"population {s.get('population')}, commit {str(s.get('commit'))[:8]}"
            f"{' (dirty)' if s.get('dirty') else ''}, {s.get('host')}")


def check_compatible(stamps, strict_dirty=True):
    """Raise unless every stamp describes the same experiment.

    `dirty` is binding because a working tree with uncommitted changes does not identify the
    code that ran: two dirty shards can share a commit and still be different programs. Pass
    `strict_dirty=False` to allow it during development, which prints what is being permitted
    rather than passing silently.
    """
    stamps = [s for s in stamps if s]
    if len(stamps) < 2:
        return
    first = stamps[0]
    for other in stamps[1:]:
        for key in BINDING:
            if key == "dirty" and not strict_dirty:
                continue
            if first.get(key) != other.get(key):
                raise RuntimeError(
                    f"these results are not the same experiment and will not be combined: "
                    f"{key} is {first.get(key)!r} in {describe(first)} and "
                    f"{other.get(key)!r} in {describe(other)}")
    if any(s.get("dirty") for s in stamps):
        if strict_dirty:
            raise RuntimeError(
                "at least one result was produced from a working tree with uncommitted "
                "changes, so the code that produced it is not identified. Commit, or pass "
                "strict_dirty=False and accept that the result is not reproducible.")
        print("note: combining results produced from an uncommitted working tree; "
              "these are not reproducible from the repository alone", file=sys.stderr)


__all__ = ["stamp", "check_compatible", "describe", "BINDING"]
