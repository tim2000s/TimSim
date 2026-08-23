"""When real people log carbohydrate, by local hour, against the template the simulator eats.

The day decomposition put 43 per cent of the mean-glucose deficit against DCLP3 in the six hours
from 21:00 to 03:00 and found the simulator running high at 06:00 to 08:00, which is the meal
template's breakfast landing on the participants' nadir. Whether the template eats at the wrong
times is checkable from records rather than arguable: the Commons treatments carry timestamps and
each user's Nightscout profile records an IANA timezone, so every carbohydrate entry has a local
hour with no inference about clocks.

This is usage data of the same standing as the announcement literature: nothing here reads a
glucose trace, so a template regrounded on it is grounded rather than fitted. DCLP3 is untouched
and remains a test.

Two caveats travel with the numbers. Logged carbohydrate under-states eaten carbohydrate, and the
under-statement is not uniform in time: unlogged intake is plausibly commonest in the evening,
which biases the evening share downward, so the real evening share is at least what this reports.
And the Commons users run oref while the day-profile deficit was measured against DCLP3, so the
clock is evidence about when people eat, not about that trial's participants specifically.

    python examples/intake_clock.py
"""
import datetime as dt
import glob
import json
import os
import sys
import zoneinfo

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from examples.commons_cohort import ROOT
from timsim import provenance
from timsim.simulation.run import DEFAULT_MEALS

OUT = os.path.join(MEASUREMENTS, "intake_clock.json")

# Entries outside this are treated as typos or pump-rewind artefacts rather than food. The lower
# bound keeps correction nibbles of a gram or two, since they are intake; the upper bound drops
# the occasional 500 g entry, which is a slip.
GRAMS_LO, GRAMS_HI = 2.0, 250.0


def user_timezone(user_dir):
    """The user's IANA timezone from any profile file, or None."""
    for path in sorted(glob.glob(os.path.join(user_dir, "**", "*profile*.json"),
                                 recursive=True)):
        try:
            data = json.load(open(path))
        except Exception:
            continue

        def find(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k.lower() == "timezone" and isinstance(v, str) and "/" in v:
                        return v
                    r = find(v)
                    if r:
                        return r
            if isinstance(o, list):
                for v in o:
                    r = find(v)
                    if r:
                        return r
        tz = find(data)
        if tz:
            try:
                return zoneinfo.ZoneInfo(tz)
            except Exception:
                continue
    return None


def carb_entries(user_dir, tz):
    """(local_hour, grams) for every carbohydrate entry, deduplicated.

    Duplicates arise because exports overlap: the same entry appears in more than one
    treatments file. Identity here is the timestamp and the grams together.
    """
    seen, out = set(), []
    for path in sorted(glob.glob(os.path.join(user_dir, "**", "*treatments*.json"),
                                 recursive=True)):
        try:
            data = json.load(open(path))
        except Exception:
            continue
        for t in data:
            stamp = t.get("created_at") or t.get("timestamp")
            grams = t.get("carbs")
            if not isinstance(stamp, str) or grams is None:
                continue
            try:
                grams = float(grams)
            except (TypeError, ValueError):
                continue
            if not (GRAMS_LO <= grams <= GRAMS_HI):
                continue
            key = (stamp, grams)
            if key in seen:
                continue
            seen.add(key)
            try:
                when = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                if when.tzinfo is None:
                    when = when.replace(tzinfo=dt.timezone.utc)
                local = when.astimezone(tz)
            except Exception:
                continue
            out.append((local.hour + local.minute / 60.0, grams,
                        local.date().toordinal()))
    return out


def template_by_hour():
    """Expected grams per hour from `DEFAULT_MEALS` at a body weight of 70 kg."""
    hours = np.arange(0, 24, 1.0)
    dens = np.zeros(24)
    for hour, hour_sd, grams, _, prob, _ in DEFAULT_MEALS:
        for h in range(24):
            # The template clips its draw to 0.5 to 23.5 rather than wrapping, so the density
            # is evaluated directly rather than circularly.
            z = (h + 0.5 - hour) / hour_sd
            dens[h] += prob * grams * np.exp(-0.5 * z * z) / (hour_sd * np.sqrt(2 * np.pi))
    return dens


def main():
    users = []
    for d in sorted(glob.glob(os.path.join(ROOT, "*"))):
        if not os.path.isdir(d):
            continue
        tz = user_timezone(d)
        if tz is None:
            continue
        rows = carb_entries(d, tz)
        if len(rows) < 50:
            continue
        days = len({r[2] for r in rows})
        users.append({"user": os.path.basename(d), "tz": str(tz), "n": len(rows),
                      "days": days, "entries_per_day": len(rows) / days,
                      "grams_per_day": sum(r[1] for r in rows) / days,
                      "hours": [r[0] for r in rows], "grams": [r[1] for r in rows]})
    if not users:
        raise SystemExit(f"no usable users under {ROOT}")

    hours = np.concatenate([u["hours"] for u in users])
    grams = np.concatenate([u["grams"] for u in users])
    hb = hours.astype(int) % 24
    total_days = sum(u["days"] for u in users)
    by_count = np.array([np.sum(hb == h) for h in range(24)], float) / total_days
    by_grams = np.array([grams[hb == h].sum() for h in range(24)], float) / total_days
    tmpl = template_by_hour()

    def share(v, hs):
        return float(100.0 * sum(v[h] for h in hs) / v.sum())

    windows = {"morning 05-10": range(5, 10), "midday 10-15": range(10, 15),
               "afternoon 15-18": range(15, 18), "evening 18-21": range(18, 21),
               "night 21-03": [21, 22, 23, 0, 1, 2], "smallhours 03-05": range(3, 5)}

    epd = [u["entries_per_day"] for u in users]
    gpd = [u["grams_per_day"] for u in users]
    report = {"provenance": provenance.stamp(), "users": len(users),
              "user_days": total_days, "entries": int(len(hours)),
              "entries_per_day": {"median": float(np.median(epd)),
                                  "p10": float(np.percentile(epd, 10)),
                                  "p90": float(np.percentile(epd, 90))},
              "grams_per_day": {"median": float(np.median(gpd)),
                                "p10": float(np.percentile(gpd, 10)),
                                "p90": float(np.percentile(gpd, 90))},
              "by_hour_grams": by_grams.tolist(), "by_hour_entries": by_count.tolist(),
              "template_by_hour_grams": tmpl.tolist(),
              "windows": {k: {"real_grams_share": share(by_grams, hs),
                              "template_grams_share": share(tmpl, hs)}
                          for k, hs in windows.items()},
              "per_user": [{k: u[k] for k in
                            ("user", "tz", "n", "days", "entries_per_day", "grams_per_day")}
                           for u in users]}
    json.dump(report, open(OUT, "w"), indent=1)

    print(f"{len(users)} users, {total_days} user-days, {len(hours)} carbohydrate entries")
    print(f"entries per day: median {np.median(epd):.2f} (p10-p90 "
          f"{np.percentile(epd, 10):.2f}-{np.percentile(epd, 90):.2f})   "
          f"template expectation 3.64")
    print(f"grams per day:   median {np.median(gpd):.0f} (p10-p90 "
          f"{np.percentile(gpd, 10):.0f}-{np.percentile(gpd, 90):.0f})   "
          f"template expectation 196 at 70 kg")
    print(f"\n{'window':18}{'real grams %':>14}{'template %':>12}")
    for k in windows:
        w = report["windows"][k]
        print(f"{k:18}{w['real_grams_share']:>14.1f}{w['template_grams_share']:>12.1f}")
    print(f"\ngrams per user-day by hour")
    print("  hour " + "".join(f"{h:>6}" for h in range(0, 24, 2)))
    print("  real " + "".join(f"{by_grams[h]:>6.1f}" for h in range(0, 24, 2)))
    print("  tmpl " + "".join(f"{tmpl[h]:>6.1f}" for h in range(0, 24, 2)))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
