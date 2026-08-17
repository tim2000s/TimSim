"""Does the 600-subject population contain the 100 unchanged?

The gate on everything downstream. If the first subjects of each class keep their names and
their parameters, every figure measured on the hundred stays valid and only the analyses using
the larger cohorts have to run again.
"""
import sys; sys.path.insert(0,"/Users/timstreet/StudioProjects/TimSim")
import numpy as np, pandas as pd
old = pd.read_csv("/Users/timstreet/.timsim-population-backup/pop100/vpop_params.csv")
new = pd.read_csv("/Users/timstreet/StudioProjects/TimSim/timsim/population/params/vpop_params.csv")
# `i` is a row identifier, not a parameter. Nothing reads it, and its numbering scheme
# changed once on purpose: it used to be a counter across the whole run, so growing the
# population renumbered every class after the first. It is now offset per class, which is
# what makes growing append-only, and comparing the two schemes shows a difference of
# exactly one class offset. The physiology is what has to match.
num = [c for c in old.columns
       if pd.api.types.is_numeric_dtype(old[c]) and c != "i"]
import os
EXPECT = int(os.environ.get("EXPECT_N", "0"))
print(f"old {len(old)} subjects, new {len(new)}")
if EXPECT and len(new) != EXPECT:
    # A gate that cannot fail when the thing it guards did not happen is not a gate. Growing
    # the population once crashed after doing the work, leaving the old file in place, and this
    # check passed by comparing that file against itself.
    print(f"\nPOPULATION IS NOT THE SIZE ASKED FOR: {len(new)} against {EXPECT}")
    raise SystemExit(1)
ok = True
for klass in ("adult","adolescent","child"):
    o = old[old.Name.str.startswith(klass)].reset_index(drop=True)
    n = new[new.Name.str.startswith(klass)].reset_index(drop=True)
    k = len(o)
    names = list(o.Name) == list(n.Name[:k])
    d = float(np.abs(o[num].to_numpy(float) - n[num].to_numpy(float)[:k]).max())
    ok &= names and d == 0.0
    print(f"  {klass:11} {k:3d} of {len(n):3d} | names match {names} | max difference {d:.2e}")
q_old = pd.read_csv("/Users/timstreet/.timsim-population-backup/pop100/vpop_quest.csv")
q_new = pd.read_csv("/Users/timstreet/StudioProjects/TimSim/timsim/population/params/vpop_quest.csv")
for c in ("CF","CR","TDI","Age"):
    m = q_new.set_index("Name")[c].reindex(q_old.Name)
    d = float(np.abs(m.to_numpy(float) - q_old[c].to_numpy(float)).max())
    ok &= d == 0.0
    print(f"  settings {c:4} max difference across the original hundred: {d:.2e}")
print("\nAPPEND-ONLY: every original subject preserved" if ok else "\nNOT APPEND-ONLY")
