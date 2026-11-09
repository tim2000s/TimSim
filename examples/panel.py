"""The first N subjects that can actually be dosed, for the producers that run a fixed panel.

Several measurements here run on a panel rather than on a cohort matched to a real population:
the ladder, the ablation, the capability table, the arbiter and the clamp comparisons all take
the first so many adults. They were taking them by name, without asking whether those subjects
have settings.

A subject that clears no combination on the titration ladder has none, and `therapy/titrate.py`
raises rather than dosing it at the loosest available, on the grounds that its settings are then
not the explanation for what it does. The error says such a subject should be excluded. Nothing
excluded it, so one undosable subject in the first forty adults failed a whole stage, six minutes
into a run and eight hours into a pipeline.

Which subjects those are is a property of the titration, so it moves whenever the physiology or
the meal schedule moves. Under the store of 24 August 2026 the first forty adults contain one,
`adult#026`, where the previous store contained none. A panel selected by name is therefore
stable in name and unstable in whether it runs at all, which is the worst of both.

This returns the first `n` subjects of a prefix that are in the store and cleared it, so a panel
keeps its size and its composition changes only when titration changes. It reports what it
dropped rather than dropping silently, because a panel quietly one subject short is a panel whose
statistics moved for a reason nobody recorded.

The natural home for this is beside `titrated_subjects` in `therapy/titrate.py`. It is here
instead because that file is one of the nine whose hash forms the code fingerprint the settings
store is validated against, and adding a selection helper to it would invalidate every store on
disk for a change that cannot affect what titration finds.
"""
import sys


def dosable(n, prefix="adult", quiet=False):
    """The first `n` subjects named `prefix#...` that have titrated settings."""
    from timsim.population import names
    from timsim.therapy import titrate

    have = set(titrate.titrated_subjects(titrate.store_for(prefix or "")))
    candidates = names(prefix) if prefix else names()
    chosen, skipped = [], []
    for name in candidates:
        if len(chosen) >= n:
            break
        (chosen if name in have else skipped).append(name)
    if skipped and not quiet:
        print(f"panel: skipped {len(skipped)} subject(s) with no titrated settings "
              f"({', '.join(skipped[:5])}{'...' if len(skipped) > 5 else ''}), "
              f"taking {len(chosen)} of the first {len(chosen) + len(skipped)}",
              file=sys.stderr, flush=True)
    if len(chosen) < n:
        raise SystemExit(f"only {len(chosen)} of the requested {n} subjects with prefix "
                         f"{prefix!r} have titrated settings. Retitrate or ask for fewer.")
    return chosen
