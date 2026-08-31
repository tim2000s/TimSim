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


def run_probe(n, out, cwd=None):
    """One probe run in a fresh interpreter, so the stashed and unstashed code both load clean."""
    root = cwd or REPO
    src = PROBE % (root, n)
    r = subprocess.run([sys.executable, "-c", src, out], cwd=root,
                       env={**os.environ, "PYTHONPATH": root},
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"probe failed:\n{r.stderr[-2000:]}")
    return json.load(open(out))


def git(*args):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)


def _ast_signature(source, path):
    """A digest of what a file does, ignoring comments, docstrings and line numbers.

    Comments never enter the AST. Docstrings do, as the first statement of a module, class or
    function, so they are removed. `include_attributes=False` drops line and column numbers,
    which otherwise move whenever a docstring above them gains a line. What remains is the
    executable content, so two files with the same signature run identically.
    """
    import ast
    tree = ast.parse(source, filename=path)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                node.body = body[1:] or [ast.Pass()]
    import hashlib
    return hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()[:16]


def prose_only_against(ref):
    """Whether every fingerprinted file differs from `ref` in prose alone.

    This is the exact form of the question the probe answers by sampling. A change confined to
    comments and docstrings cannot alter a run, so no number of subjects is needed to establish
    it, and unlike the probe it works on a change that has already been committed.

    Returns (verdict, per-file findings). A file that cannot be read at `ref`, or that does not
    parse, counts against the verdict rather than for it.
    """
    from timsim.therapy import titrate
    findings, ok = [], True
    for rel in titrate._CODE:
        disk_path = os.path.join(REPO, "timsim", rel)
        show = git("show", f"{ref}:timsim/{rel}")
        try:
            with open(disk_path) as fh:
                now = _ast_signature(fh.read(), rel)
        except (OSError, SyntaxError) as exc:
            findings.append((rel, "unreadable on disk", str(exc)[:80]))
            ok = False
            continue
        if show.returncode != 0:
            findings.append((rel, "absent at the reference", ""))
            ok = False
            continue
        try:
            was = _ast_signature(show.stdout, rel)
        except SyntaxError as exc:
            findings.append((rel, "does not parse at the reference", str(exc)[:80]))
            ok = False
            continue
        same = was == now
        findings.append((rel, "prose only" if same else "code changed",
                         "" if same else f"{was} to {now}"))
        ok = ok and same
    return ok, findings


def _probe_against_worktree(a, titrate):
    """Probe the same subjects in a separate checkout of `a.worktree`, rather than by stashing.

    A committed change cannot be stashed, and stashing whatever else happens to be uncommitted
    compares the working tree with itself. This checks out the reference commit somewhere else
    and runs the same probe there.

    The population and the settings store are not in git, so the checkout has neither. They are
    symlinked from this one: both sides have to read the same subjects and the same settings or
    the comparison measures the population rather than the change.
    """
    import shutil
    import tempfile

    wt = tempfile.mkdtemp(prefix="restamp-worktree-")
    shutil.rmtree(wt)
    r = git("worktree", "add", "-q", "--detach", wt, a.worktree)
    if r.returncode != 0:
        raise SystemExit(f"could not create a worktree at {a.worktree}:\n{r.stderr}")
    try:
        src = os.path.join(REPO, "timsim", "population", "params")
        dst = os.path.join(wt, "timsim", "population", "params")
        os.makedirs(dst, exist_ok=True)
        for f in os.listdir(src):
            link = os.path.join(dst, f)
            if not os.path.exists(link):
                os.symlink(os.path.join(src, f), link)

        tmp = os.path.join(REPO, "docs", "measurements", "rebuild")
        os.makedirs(tmp, exist_ok=True)
        new_p = os.path.join(tmp, "_restamp_new.json")
        old_p = os.path.join(tmp, "_restamp_old.json")
        print(f"probing {a.subjects} subjects with the change in place")
        new = run_probe(a.subjects, new_p)
        print(f"probing {a.subjects} subjects at {a.worktree} in {wt}")
        old = run_probe(a.subjects, old_p, cwd=wt)
        return old, new
    finally:
        git("worktree", "remove", "--force", wt)


def _report_and_stamp(a, titrate, store, was, now, old, new, how):
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
        {"from": was, "to": now, "subjects_verified": sorted(old), "how": how,
         "note": a.note or "verified inert on the reference driver, no measure differed"})
    store["meta"]["code"] = now
    tmp_out = titrate.STORE + ".partial"
    with open(tmp_out, "w") as fh:
        json.dump(store, fh, indent=1, default=str)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_out, titrate.STORE)
    print(f"re-stamped {titrate.STORE} from {was} to {now}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=3,
                    help="how many subjects to verify. More is slower and stronger.")
    ap.add_argument("--check", action="store_true", help="report and change nothing")
    ap.add_argument("--note", default="", help="what changed, recorded in the store")
    ap.add_argument("--worktree", metavar="REF",
                    help="a git ref to probe against in a separate checkout rather than by "
                         "stashing. Use this when the change is already committed. The "
                         "population and the settings store are shared with this checkout by "
                         "symlink, since they are not in git and both sides must read the same "
                         "ones for the comparison to mean anything.")
    ap.add_argument("--against", metavar="REF",
                    help="a git ref the store's fingerprint was produced at. Every "
                         "fingerprinted file is compared with that ref by abstract syntax "
                         "tree, and a difference confined to comments and docstrings is "
                         "proved inert rather than sampled. Use this when the change is "
                         "already committed, which the probe cannot handle since it stashes.")
    a = ap.parse_args()

    from timsim.therapy import titrate

    store = json.load(open(titrate.STORE))
    was = store["meta"].get("code")
    now = titrate.code_fingerprint()
    if was == now:
        print(f"The store already matches the code on disk at {now}. Nothing to do.")
        return
    print(f"store fingerprint {was}\ncode on disk      {now}\n")

    if a.against:
        ok, findings = prose_only_against(a.against)
        width = max(len(f[0]) for f in findings)
        for rel, verdict, detail in findings:
            print(f"  {rel:<{width}}  {verdict}{'  ' + detail if detail else ''}")
        if not ok:
            raise SystemExit(f"\nAgainst {a.against} the change reaches executable code, so it "
                             f"may reach the ladder. The store is unchanged. Retitrate.")
        print(f"\nEvery fingerprinted file differs from {a.against} in comments and docstrings "
              f"alone,\nso the change cannot alter a run and no probe is needed.")
        if a.check:
            print("--check given, so the store is unchanged.")
            return
        store["meta"].setdefault("restamped", []).append(
            {"from": was, "to": now, "method": "ast", "reference": a.against,
             "files_compared": list(__import__("timsim.therapy.titrate", fromlist=["x"])._CODE),
             "note": a.note or f"prose-only against {a.against}, proved by syntax tree"})
        store["meta"]["code"] = now
        tmp_out = titrate.STORE + ".partial"
        with open(tmp_out, "w") as fh:
            json.dump(store, fh, indent=1, default=str)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_out, titrate.STORE)
        print(f"re-stamped {titrate.STORE} from {was} to {now}")
        return

    if a.worktree:
        old, new = _probe_against_worktree(a, titrate)
        _report_and_stamp(a, titrate, store, was, now, old, new,
                          how=f"probed against {a.worktree} in a separate checkout")
        return

    if not git("stash", "list").stdout.strip() == "":
        raise SystemExit("There is already a stash. Clear it first, since this uses one.")
    dirty = git("status", "--porcelain").stdout.strip()
    if not dirty:
        raise SystemExit("The working tree is clean, so there is no change to stash and the "
                         "fingerprints differ for some other reason. Retitrate.")

    # The stash has to contain the change being tested, and nothing checked that. With the change
    # committed and only an output file uncommitted, this stashed the output, ran the same code
    # twice, and reported three subjects identical having compared nothing. A check that passes
    # when it has tested nothing is worse than no check, so it now refuses unless a fingerprinted
    # file actually differs from HEAD. Recorded as issue 47.
    touched = [f for f in titrate._CODE
               if git("diff", "--quiet", "HEAD", "--", "timsim/" + f).returncode != 0]
    if not touched:
        raise SystemExit(
            "None of the fingerprinted files differ from HEAD, so stashing would compare the "
            "working tree with itself and prove nothing. The change is committed. Use "
            "--worktree REF against the commit before it, which runs the probe in a separate "
            "checkout instead of stashing.")
    print(f"fingerprinted files changed in the working tree: {', '.join(touched)}")

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
