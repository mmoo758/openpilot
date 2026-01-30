/**
 * Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.
 *
 * This file is part of sunnypilot and is licensed under the MIT License.
 * See the LICENSE.md file in the root directory for more details.
 */

#include "selfdrive/ui/sunnypilot/qt/offroad/settings/vehicle/tesla_settings.h"
#include "common/params.h"
#include "common/util.h"

TeslaSettings::TeslaSettings(QWidget *parent) : BrandSettingsInterface(parent) {
  // Cooperative steering - use LKAS mode
  constexpr int lkasMinSpeedKmh = 24; // minimum speed for LKAS (enforced by Tesla firmware)
  Params params;
  bool is_metric = params.getBool("IsMetric");
  QString unit = is_metric ? "km/h" : "mph";
  int display_speed;
  if (is_metric) {
    display_speed = lkasMinSpeedKmh;
  } else {
    display_speed = static_cast<int>(std::round(lkasMinSpeedKmh * KM_TO_MILE));
  }

  const QString lkas_steering_desc = tr("Enables LKAS steering control interface. Provides OEM-like torque blending for speeds above %1 %2.")
                                     .arg(display_speed)
                                     .arg(unit);

  lkasSteeringToggle = new ParamControlSP(
    "TeslaLkasSteering",
    tr("LKAS Steering Control"),
    lkas_steering_desc,
    "../assets/offroad/icon_openpilot.png",
    this
  );
  list->addItem(lkasSteeringToggle);
  lkasSteeringToggle->showDescription();

  // Cooperative steering - angle manipulation
  const QString coop_desc = tr("Converts light driver input to steering angle at all speeds. It will blend with LKAS torque blending if enabled.");

  coopSteeringToggle = new ParamControlSP(
    "TeslaCoopSteering",
    tr("Extended Cooperative Steering"),
    coop_desc,
    "",
    this
  );
  list->addItem(coopSteeringToggle);
  coopSteeringToggle->showDescription();
}

void TeslaSettings::updateSettings() {
  lkasSteeringToggle->setEnabled(offroad);
  coopSteeringToggle->setEnabled(offroad);
}
