"""Combine shards of a run, and refuse when they are not the same experiment.

Splitting 1,440 independent runs across two machines is arithmetically trivial and is the
easiest way yet devised to produce a number nobody can account for. The failure is quiet: both
machines complete, both write plausible results, and the merged total is a mixture of two
populations or two versions of the code with nothing in the output to say so.

So this checks before it combines. The population, the titrated settings, the commit and
whether the working tree was clean all have to agree. Everything else is reported.

    python examples/merge_shards.py out.json shard1.json shard2.json ...

Shards are taken by position from the same run list, so a run appearing in two shards means the
lists were not the same and the merge stops rather than picking one.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import argparse
import json
from collections import Counter

from timsim import provenance


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("shards", nargs="+")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="combine results produced from an uncommitted working tree, which "
                         "are not reproducible from the repository alone")
    a = ap.parse_args()

    loaded = [json.load(open(p)) for p in a.shards]
    for path, d in zip(a.shards, loaded):
        sh = d.get("shard", {})
        st = d.get("provenance", {})
        print(f"  {os.path.basename(path):32} shard {sh.get('index','?')}/{sh.get('of','?')}"
              f"  {len(d.get('runs', []))} runs  {provenance.describe(st) if st else 'UNSTAMPED'}")

    if any(not d.get("provenance") for d in loaded):
        raise SystemExit("\nat least one shard carries no provenance stamp, so it cannot be "
                         "shown to belong with the others. Rerun it with a version that "
                         "stamps its output.")

    provenance.check_compatible([d["provenance"] for d in loaded],
                                strict_dirty=not a.allow_dirty)

    expected = {d.get("shard", {}).get("of") for d in loaded}
    if len(expected) != 1:
        raise SystemExit(f"\nshards disagree about how many there are: {expected}")
    of = expected.pop()
    seen = sorted(d.get("shard", {}).get("index") for d in loaded)
    if of and seen != list(range(1, of + 1)):
        print(f"\nwarning: have shards {seen} of {of}; the merge is incomplete",
              file=sys.stderr)

    runs, keys = [], Counter()
    for d in loaded:
        for r in d["runs"]:
            key = (r.get("cohort"), r.get("controller"), r.get("bench"), r.get("name"))
            keys[key] += 1
            runs.append(r)
    dupes = [k for k, c in keys.items() if c > 1]
    if dupes:
        raise SystemExit(f"\n{len(dupes)} runs appear in more than one shard, so the shards "
                         f"were not slices of the same list: e.g. {dupes[0]}")

    total = loaded[0].get("shard", {}).get("runs_total")
    base = dict(loaded[0])
    base["runs"] = runs
    base["shard"] = {"merged_from": len(loaded), "of": of, "runs": len(runs),
                     "runs_total": total}
    base["provenance"] = {**loaded[0]["provenance"],
                          "hosts": sorted({d["provenance"].get("host") for d in loaded})}
    json.dump(base, open(a.out, "w"), indent=1)
    print(f"\ncombined {len(runs)} runs"
          + (f" of an expected {total}" if total else "")
          + f" from {len(loaded)} shards into {a.out}")
    if total and len(runs) != total:
        print(f"warning: {total - len(runs)} runs are missing", file=sys.stderr)


if __name__ == "__main__":
    main()
