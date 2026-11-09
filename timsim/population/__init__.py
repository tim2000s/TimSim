"""Virtual population: generation, screening, and access to the shipped subjects."""
import os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS_DIR = os.path.join(HERE, "params")
PATIENT_FILE = os.path.join(PARAMS_DIR, "vpop_params.csv")
THERAPY_FILE = os.path.join(PARAMS_DIR, "vpop_quest.csv")
REPORT_FILE = os.path.join(PARAMS_DIR, "vpop_report.json")


def available():
    """True once a population has been generated into the package."""
    return os.path.exists(PATIENT_FILE)


def patients():
    """The subject parameter table, in simglucose's own column layout."""
    if not available():
        raise FileNotFoundError(
            "No population found. Generate one with:\n"
            "    python -m timsim.population.build --n 100"
        )
    return pd.read_csv(PATIENT_FILE)


def therapy():
    """Carbohydrate ratio, correction factor, age and daily dose per subject."""
    return pd.read_csv(THERAPY_FILE)


def names(klass=None):
    h = _hovorka(klass, "params") if klass else None
    n = (patients() if h is None else h).Name
    return list(n[n.str.startswith(klass)] if klass else n)


def _hovorka(name, which):
    """The Hovorka table for a `hovorka#` subject, or None for an S2008 one."""
    from . import hovorka
    if not str(name).startswith(hovorka.PREFIX):
        return None
    path = hovorka.PATIENT_FILE if which == "params" else hovorka.THERAPY_FILE
    if not os.path.exists(path):
        raise FileNotFoundError(
            "No Hovorka population found. Generate one with:\n"
            "    python -m timsim.population.hovorka --n 100")
    return pd.read_csv(path)


def params_for(name):
    p = _hovorka(name, "params")
    p = patients() if p is None else p
    row = p.loc[p.Name == name]
    if row.empty:
        raise KeyError(f"no subject named {name}")
    return row.squeeze()


def therapy_for(name):
    q = _hovorka(name, "therapy")
    q = therapy() if q is None else q
    row = q.loc[q.Name == name]
    if row.empty:
        raise KeyError(f"no therapy settings for {name}")
    return row.squeeze()
