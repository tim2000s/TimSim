"""Steady-state closure for a UVA/Padova 2008 parameter set.

Of the 62 columns in a simglucose patient row, only about half are free. The rest are
either constant across the published cohort or determined exactly by the model's own
balance equations at the basal steady state. Every relation below was verified against
all 30 published subjects to floating-point tolerance, which is what makes generating
new subjects a matter of sampling the free parameters and closing the rest rather than
sampling 62 numbers and hoping they are consistent.

The relations, in the order they resolve:

    Gpb   = Gb * Vg                          plasma glucose mass from concentration
    Gtb   = (k1*Gpb - EGPb + Fsnc) / k2      tissue glucose from the glucose balance
    Vm0   = (EGPb - Fsnc) * (Km0 + Gtb)/Gtb  utilisation scaled to meet basal disposal
    Ipb   = Ib * Vi                          plasma insulin mass from concentration
    m30   = HEb * m1 / (1 - HEb)             hepatic extraction
    Ilb   = m2 * Ipb / (m1 + m30)            liver insulin from the insulin balance
    u2ss  = (m2 + m4)*Ipb - m1*Ilb           the infusion that holds that steady state
    isc1ss= u2ss / (kd + ka1)                subcutaneous compartments at steady state
    isc2ss= kd * isc1ss / ka2
    kp1   = EGPb + kp2*Gpb + kp3*Ib          endogenous production intercept
    Rdb   = EGPb                             disposal equals production at steady state

A parameter set that violates any positivity requirement here is not a person, and
`close()` says so rather than producing a subject that integrates to nonsense.
"""
import numpy as np

# Constant across all 30 published subjects, so held fixed rather than sampled.
CONSTANTS = {
    "x0_ 1": 0.0, "x0_ 2": 0.0, "x0_ 3": 0.0, "x0_ 7": 0.0,
    "HEb": 0.6, "f": 0.9, "ke1": 0.0005, "ke2": 339.0, "Fsnc": 1.0,
    "dosekempt": 90000.0, "patient_history": 0,
}

# Sampled independently. Everything not in this list and not in CONSTANTS is derived.
FREE = ["BW", "EGPb", "Gb", "Ib", "kabs", "kmax", "kmin", "b", "d", "Vg", "Vi",
        "Vmx", "Km0", "k2", "k1", "p2u", "m1", "m5", "CL", "m2", "m4", "ki",
        "kp2", "kp3", "PCRb", "kd", "ksc", "ka1", "ka2"]

# Column order simglucose expects, so a generated row is a drop-in for a published one.
COLUMNS = ["Name", "i",
           "x0_ 1", "x0_ 2", "x0_ 3", "x0_ 4", "x0_ 5", "x0_ 6", "x0_ 7", "x0_ 8",
           "x0_ 9", "x0_10", "x0_11", "x0_12", "x0_13",
           "BW", "EGPb", "Gb", "Ib", "kabs", "kmax", "kmin", "b", "d", "Vg", "Vi",
           "Ipb", "Vmx", "Km0", "k2", "k1", "p2u", "m1", "m5", "CL", "HEb", "m2",
           "m4", "m30", "Ilb", "ki", "kp2", "kp3", "f", "Gpb", "ke1", "ke2", "Fsnc",
           "Gtb", "Vm0", "Rdb", "PCRb", "kd", "ksc", "ka1", "ka2", "dosekempt",
           "u2ss", "isc1ss", "isc2ss", "kp1", "patient_history"]


class NotViable(ValueError):
    """The sampled parameters do not admit a physiological steady state."""


def close(free, name, index):
    """Complete a free-parameter dict into a full simglucose patient row.

    Raises NotViable when the balance equations have no positive solution, which is the
    first and cheapest of the screening gates.
    """
    p = dict(CONSTANTS)
    p.update({k: float(free[k]) for k in FREE})
    p["Name"], p["i"] = name, index

    if p["kmin"] >= p["kmax"]:
        raise NotViable("gastric emptying minimum is not below its maximum")
    if not (0 < p["b"] < 1) or not (0 < p["d"] < 1):
        raise NotViable("gastric emptying shape parameters outside the unit interval")

    Gpb = p["Gb"] * p["Vg"]
    Gtb = (p["k1"] * Gpb - p["EGPb"] + p["Fsnc"]) / p["k2"]
    if Gtb <= 0:
        raise NotViable("tissue glucose steady state is not positive")
    if p["EGPb"] <= p["Fsnc"]:
        raise NotViable("basal production does not exceed insulin-independent uptake")

    Vm0 = (p["EGPb"] - p["Fsnc"]) * (p["Km0"] + Gtb) / Gtb
    Ipb = p["Ib"] * p["Vi"]
    m30 = p["HEb"] * p["m1"] / (1.0 - p["HEb"])
    Ilb = p["m2"] * Ipb / (p["m1"] + m30)
    u2ss = (p["m2"] + p["m4"]) * Ipb - p["m1"] * Ilb
    if u2ss <= 0:
        raise NotViable("basal insulin requirement is not positive")

    isc1ss = u2ss / (p["kd"] + p["ka1"])
    isc2ss = p["kd"] * isc1ss / p["ka2"]
    kp1 = p["EGPb"] + p["kp2"] * Gpb + p["kp3"] * p["Ib"]

    p.update({
        "Gpb": Gpb, "Gtb": Gtb, "Vm0": Vm0, "Ipb": Ipb, "m30": m30, "Ilb": Ilb,
        "u2ss": u2ss, "isc1ss": isc1ss, "isc2ss": isc2ss, "kp1": kp1,
        "Rdb": p["EGPb"],
        "x0_ 4": Gpb, "x0_ 5": Gtb, "x0_ 6": Ipb, "x0_ 8": p["Ib"], "x0_ 9": p["Ib"],
        "x0_10": Ilb, "x0_11": isc1ss, "x0_12": isc2ss, "x0_13": Gpb,
    })
    return {c: p[c] for c in COLUMNS}


def verify(published):
    """Check every relation against the published cohort. Returns the worst residual."""
    worst = 0.0
    for _, row in published.iterrows():
        free = {k: row[k] for k in FREE}
        got = close(free, row["Name"], row["i"])
        for c in COLUMNS:
            if c in ("Name", "i", "patient_history"):
                continue
            a, b = float(got[c]), float(row[c])
            scale = max(abs(b), 1e-9)
            worst = max(worst, abs(a - b) / scale)
    return worst


def basal_rate(params):
    """Basal insulin in U/min, the quantity a pump would be programmed with."""
    return float(params["u2ss"]) * float(params["BW"]) / 6000.0


def fasting_glucose(params):
    return float(params["Gb"])


__all__ = ["close", "verify", "basal_rate", "fasting_glucose", "NotViable",
           "FREE", "CONSTANTS", "COLUMNS"]
