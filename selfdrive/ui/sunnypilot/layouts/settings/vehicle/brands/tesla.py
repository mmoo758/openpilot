"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from opendbc.sunnypilot.car.tesla.values import TeslaFlagsSP
from openpilot.selfdrive.ui.sunnypilot.layouts.settings.vehicle.brands.base import BrandSettings
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.sunnypilot.widgets.list_view import multiple_button_item_sp, toggle_item_sp

class TeslaSettings(BrandSettings):
  def __init__(self):
    super().__init__()
    self.coop_steering_toggle = toggle_item_sp(tr("Cooperative Steering"), "", param="TeslaCoopSteering")
    self.mads_screen_button = multiple_button_item_sp(
      title=lambda: tr("MADS Screen Button"),
      description="",
      buttons=[lambda: tr("Off"), lambda: tr("3 Finger"), lambda: tr("4 Finger"), lambda: tr("5 Finger")],
      param="TeslaMadsScreenButton",
      inline=False,
    )
    self.items = [self.coop_steering_toggle, self.mads_screen_button]

  def update_settings(self):
    coop_steering_desc = (
      f"{tr('Converts light steering input into steering-wheel rotation.')}<br>" +
      f"{tr('The faster you go, the stiffer the steering gets.')}"
    )

    enable_offroad_msg = tr("Enable \"Always Offroad\" in Device panel, or turn vehicle off to toggle.")
    if not ui_state.is_offroad():
      coop_steering_desc = f"<b>{enable_offroad_msg}</b><br><br>{coop_steering_desc}"

    self.coop_steering_toggle.set_description(coop_steering_desc)

    self.coop_steering_toggle.action_item.set_enabled(ui_state.is_offroad())

    has_vehicle_bus = ui_state.CP_SP is not None and bool(ui_state.CP_SP.flags & TeslaFlagsSP.HAS_VEHICLE_BUS)
    self.mads_screen_button.set_visible(has_vehicle_bus)

    mads_screen_button_desc = tr("Use a multi-finger press on the infotainment display as a MADS button.\n" +
                                 "This allows the use of full MADS functionality when enabled.\n" +
                                 "<b>Note: Setting this to Off may reset your MADS settings to default.</b>")
    if not ui_state.is_offroad():
      mads_screen_button_disabled_msg = tr("Enable \"Always Offroad\" in Device panel, or turn vehicle off to change.")
      mads_screen_button_desc = f"<b>{mads_screen_button_disabled_msg}</b><br><br>{mads_screen_button_desc}"
    self.mads_screen_button.set_description(mads_screen_button_desc)
    self.mads_screen_button.action_item.set_enabled(ui_state.is_offroad())
