"""The insulin action curve, shared by everything that needs insulin on board.

A bilinear activity curve with a peak partway through the duration of action. It is the
same shape the correction loop has always used here, lifted out so that the pump limit
enforcer and any algorithm under test read insulin on board off one definition rather
than three slightly different ones.
"""
DIA_MIN = 300.0           # duration of insulin action
PEAK_MIN = 75.0           # activity peak


def iob_fraction(age_min, dia_min=DIA_MIN, peak_min=PEAK_MIN):
    """Fraction of a bolus still to act, `age_min` after it was given."""
    if age_min <= 0:
        return 1.0
    if age_min >= dia_min:
        return 0.0
    p, d = float(peak_min), float(dia_min)
    if age_min < p:
        return 1.0 - (age_min ** 2) / (p * d)
    return ((d - age_min) ** 2) / (d * (d - p))


def iob(minute, doses, dia_min=DIA_MIN, peak_min=PEAK_MIN):
    """Insulin on board at `minute`, from an iterable of (minute, units)."""
    return float(sum(u * iob_fraction(minute - m, dia_min, peak_min) for m, u in doses))


__all__ = ["iob_fraction", "iob", "DIA_MIN", "PEAK_MIN"]
