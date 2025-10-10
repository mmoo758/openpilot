"""
Pause Lateral on Steering Override Feature

Mirrors BlinkerPauseLateralControl pattern: when enabled, lateral control
is paused whenever the driver is applying steering torque (steeringPressed).
"""
from typing import TYPE_CHECKING

from cereal import car

from openpilot.common.params import Params


class OverridePauseLateral:
  def __init__(self):
    self.params = Params()
    self.enabled = self.params.get_bool("PauseLateralOnOverride")

  def get_params(self) -> None:
    self.enabled = self.params.get_bool("PauseLateralOnOverride")

  def update(self, CS) -> bool:
    if not self.enabled:
      return False
    return bool(CS.steeringPressed)
