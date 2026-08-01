"""Virtual subjects, including one whose insulin sensitivity varies."""

from .varying import VaryingPatient, from_population
__all__ = ["VaryingPatient", "from_population"]
