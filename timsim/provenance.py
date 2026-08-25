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
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# What must agree before two sets of results describe the same experiment. Everything else in
# the stamp is context: useful when a result looks odd, not grounds for refusing to merge.
#
# `settings` is here because titrated settings are an input to every run, not a derived note.
# They are generated locally and never committed, so two machines can sit at the same commit
# with the same population and different settings: titration takes a subject list, and a run
# that titrated a different subset writes a different store. Every subject's correction factor
# and basal rate come from it, so shards that disagree are not the same experiment. It was
# recorded and not enforced, and `merge_shards.py` would have combined them.
#
# `simglucose` is here because it is the patient model. The lock file pins it, and two results
# produced against different versions are two models however well the arithmetic lines up.
BINDING = ("population", "settings", "commit", "dirty", "simglucose")


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
    """A digest of the titrated settings, which are as much an input as the population.

    Over the settings themselves rather than over the file. What binds a result is the dose each
    subject was given: its adopted scales, and whether it cleared the floors at all, since a
    subject that did not is excluded from every cohort. The rest of the file is provenance about
    the titration, and hashing it made the record of a verification change the identity of the
    thing verified.

    That is not hypothetical. Re-stamping a store on 25 August 2026, to record that a code change
    had been checked and found inert, moved this digest from 8000d3ede7314482 to 046e0da5bc380688
    while leaving all 330 subjects and all 306 adopted settings identical. Every measurement taken
    after it then declared itself a different experiment from the baseline it was meant to extend,
    and `check_compatible` would have refused to combine two sets of figures that were computed on
    the same doses.

    Digesting the settings makes the fingerprint answer the question it is asked: were these
    figures measured on the same settings. Fingerprints recorded before this change hash the whole
    file and will not match one computed here, so a stored figure older than this compares by the
    archived store rather than by the digest.
    """
    path = os.path.join(REPO, "timsim", "population", "params", "titrated_settings.json")
    try:
        with open(path) as fh:
            store = json.load(fh)
    except (OSError, ValueError):
        return None
    subjects = store.get("subjects", {})
    payload = [(name, r.get("scale"), r.get("basal_scale"), bool(r.get("found")))
               for name, r in sorted(subjects.items())]
    return hashlib.sha256(repr(payload).encode()).hexdigest()[:16]


def _simglucose_version():
    """The installed patient model's version, from the distribution rather than the module.

    `simglucose` defines no `__version__`, so reading that attribute returned the string
    "unknown" on every run of every machine. Since `simglucose` is one of the binding fields,
    that made the field worse than absent: two results computed under different versions of the
    patient model compared as compatible, because both claimed ignorance in the same words.
    The distribution metadata carries the version and is what is read now.
    """
    try:
        from importlib import metadata
        return metadata.version("simglucose")
    except Exception:
        pass
    try:
        import simglucose
        return getattr(simglucose, "__version__", None)
    except Exception:
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
    out["simglucose"] = _simglucose_version()
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
