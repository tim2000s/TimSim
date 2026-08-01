"""Sensor artefacts the physiological model does not produce."""

from .realism import add_sensor_noise, apply, inject_compression_lows
__all__ = ["apply", "add_sensor_noise", "inject_compression_lows"]
