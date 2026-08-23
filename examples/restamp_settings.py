"""Re-stamp the titration store's code fingerprint after a change proved not to reach it.

The fingerprint in `therapy/titrate.py` covers nine files and refuses a store produced by code
that no longer matches. It is deliberately coarse: it hashes the files rather than reasoning
about what a change does, because the failure it exists to prevent is a settings ladder run
against different physiology, and a fingerprint that tried to judge relevance would be a
fingerprint somebody could argue with.

That coarseness costs a retitration whenever one of those files gains something switched off by
default. A retitration is not free, it moves the settings store, and every measurement bound to
the old store then has to be repeated even though nothing about the settings changed.

So this offers the only alternative that keeps the guard meaningful: prove the change did not
reach the titration, on the runs the titration is made of, and record the proof beside the new
fingerprint. It re-runs a sample of subjects under the reference driver at the rung the ladder
starts from, with the working tree as it is and with the change stashed, and re-stamps only when
every measure agrees exactly. Anything else leaves the store alone and says so.

What it writes into the store's meta is a `restamped` list, so a store carrying one says how it
came to differ from the code that produced it and what was checked. A store that has been
re-stamped is weaker evidence than one that was titrated, and it should be readable as such.

    python examples/restamp_settings.py --check          # report, change nothing
    python examples/restamp_settings.py --subjects 5     # verify and re-stamp
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

PROBE = r'''
import json, sys
import numpy as np
sys.path.insert(0, %r)
from timsim.simulation.run import simulate
from timsim.therapy import profile as pm
from timsim.population import names
out = {}
for n in names()[:%d]:
    r = simulate(n, days=28, seed=0, layers=("physiology", "behaviour", "sensor", "site"),
                 controller="trend", profile=pm.for_subject(n))
    c = np.asarray(r.cgm, float)
    out[n] = [round(float(np.mean(c)), 9), round(float(np.std(c)), 9),
              round(float(100 * np.mean(c < 70)), 9),
              round(float(100 * np.mean(c < 54)), 9),
              round(float(100 * np.mean((c >= 70) & (c <= 180))), 9), bool(r.completed)]
json.dump(out, open(sys.argv[1], "w"), indent=1)
'''


def run_probe(n, out):
    """One probe run in a fresh interpreter, so the stashed and unstashed code both load clean."""
    src = PROBE % (REPO, n)
    r = subprocess.run([sys.executable, "-c", src, out], cwd=REPO,
                       env={**os.environ, "PYTHONPATH": REPO},
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"probe failed:\n{r.stderr[-2000:]}")
    return json.load(open(out))


def git(*args):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=3,
                    help="how many subjects to verify. More is slower and stronger.")
    ap.add_argument("--check", action="store_true", help="report and change nothing")
    ap.add_argument("--note", default="", help="what changed, recorded in the store")
    a = ap.parse_args()

    from timsim.therapy import titrate

    store = json.load(open(titrate.STORE))
    was = store["meta"].get("code")
    now = titrate.code_fingerprint()
    if was == now:
        print(f"The store already matches the code on disk at {now}. Nothing to do.")
        return
    print(f"store fingerprint {was}\ncode on disk      {now}\n")

    if not git("stash", "list").stdout.strip() == "":
        raise SystemExit("There is already a stash. Clear it first, since this uses one.")
    dirty = git("status", "--porcelain").stdout.strip()
    if not dirty:
        raise SystemExit("The working tree is clean, so there is no change to stash and the "
                         "fingerprints differ for some other reason. Retitrate.")

    tmp = os.path.join(REPO, "docs", "measurements", "rebuild")
    os.makedirs(tmp, exist_ok=True)
    new_p, old_p = os.path.join(tmp, "_restamp_new.json"), os.path.join(tmp, "_restamp_old.json")

    print(f"probing {a.subjects} subjects with the change in place")
    new = run_probe(a.subjects, new_p)
    if git("stash", "-q").returncode != 0:
        raise SystemExit("stash failed, nothing changed")
    try:
        print(f"probing {a.subjects} subjects with the change stashed")
        old = run_probe(a.subjects, old_p)
    finally:
        if git("stash", "pop", "-q").returncode != 0:
            raise SystemExit("THE STASH DID NOT POP. Run `git stash pop` by hand before "
                             "anything else. Your change is in the stash, not lost.")

    same = [k for k in old if old[k] == new[k]]
    for k in sorted(old):
        print(f"  {k}: {'identical' if old[k] == new[k] else f'{old[k]} vs {new[k]}'}")

    if len(same) != len(old):
        raise SystemExit("\nThe change alters runs, so it may alter what the ladder finds. "
                         "The store is unchanged. Retitrate.")
    print(f"\nAll {len(old)} subjects identical, so the change does not reach the titration.")
    if a.check:
        print("--check given, so the store is unchanged.")
        return

    store["meta"].setdefault("restamped", []).append(
        {"from": was, "to": now, "subjects_verified": sorted(old),
         "note": a.note or "verified inert on the reference driver, no measure differed"})
    store["meta"]["code"] = now
    tmp_out = titrate.STORE + ".partial"
    with open(tmp_out, "w") as fh:
        json.dump(store, fh, indent=1, default=str)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_out, titrate.STORE)
    print(f"re-stamped {titrate.STORE} from {was} to {now}")


if __name__ == "__main__":
    main()
