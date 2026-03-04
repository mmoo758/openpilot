#!/usr/bin/env python3

import math
import numpy as np

from cereal import messaging, car
from opendbc.car.vehicle_model import VehicleModel
from openpilot.common.realtime import DT_CTRL, Ratekeeper
from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog

from opendbc.car.interfaces import get_interface_attr

LongCtrlState = car.CarControl.Actuators.LongControlState
MAX_LAT_ACCEL = 3.0
MAX_LAT_JERK = 1.5


def joystickd_thread():
  params = Params()
  cloudlog.info("joystickd is waiting for CarParams")
  CP = messaging.log_from_bytes(params.get("CarParams", block=True), car.CarParams)
  VM = VehicleModel(CP)

  # get max angle from car brand params
  max_angle = 450
  try:
    car_params = get_interface_attr('CarControllerParams')
    if car_params and CP.carFingerprint in car_params:
      angle_limits = car_params[CP.carFingerprint].ANGLE_LIMITS
      if hasattr(angle_limits, 'steerAngleMax'):
        max_angle = angle_limits.steerAngleMax
  except Exception:
    pass

  sm = messaging.SubMaster(['carState', 'onroadEvents', 'liveParameters', 'selfdriveState', 'testJoystick'], frequency=1. / DT_CTRL)
  pm = messaging.PubMaster(['carControl', 'controlsState'])

  rk = Ratekeeper(100, print_delay_threshold=None)
  prev_curvature = 0.0
  while 1:
    sm.update(0)

    cc_msg = messaging.new_message('carControl')
    cc_msg.valid = True
    CC = cc_msg.carControl
    CC.enabled = sm['selfdriveState'].enabled
    CC.latActive = sm['selfdriveState'].active and not sm['carState'].steerFaultTemporary and not sm['carState'].steerFaultPermanent
    CC.longActive = CC.enabled and CP.openpilotLongitudinalControl
    CC.cruiseControl.cancel = sm['carState'].cruiseState.enabled and (not CC.enabled or not CP.pcmCruise)
    CC.hudControl.leadDistanceBars = 2

    actuators = CC.actuators

    # reset joystick if it hasn't been received in a while
    should_reset_joystick = sm.recv_frame['testJoystick'] == 0 or (sm.frame - sm.recv_frame['testJoystick'])*DT_CTRL > 0.2

    if not should_reset_joystick:
      joystick_axes = sm['testJoystick'].axes
      if hasattr(sm['testJoystick'], 'buttons') and sm['testJoystick'].buttons and sm['testJoystick'].buttons[0] == 1:
        CC.cruiseControl.cancel = True
    else:
      joystick_axes = [0.0, 0.0]

    if CC.longActive:
      actuators.accel = 4.0 * float(np.clip(joystick_axes[0], -1, 1))
      actuators.longControlState = LongCtrlState.pid if sm['carState'].vEgo > CP.vEgoStopping else LongCtrlState.stopping
      CC.cruiseControl.resume = actuators.accel > 0.0

    if CC.latActive:
      steer_input = float(np.clip(joystick_axes[1], -1, 1))

      # limit lateral acceleration and jerk for non-torque cars
      v_ego = sm['carState'].vEgo
      roll = sm['liveParameters'].roll
      max_curvature = MAX_LAT_ACCEL / max(v_ego ** 2, 5)
      max_curvature_rate = (MAX_LAT_JERK / max(v_ego ** 2, 5))

      max_curvature_from_angle = abs(VM.calc_curvature(math.radians(max_angle), v_ego, roll))
      target_curvature = steer_input * min(max_curvature, max_curvature_from_angle)

      # rate-imit only when moving away from the center
      # snappy centering helps user with correcting the input
      up = float(np.clip(target_curvature - prev_curvature, -np.inf, max_curvature_rate * DT_CTRL))
      down = float(np.clip(target_curvature - prev_curvature, -max_curvature_rate * DT_CTRL, np.inf))
      curvature = prev_curvature + (up if target_curvature > 0.0 else down)

      angle = math.degrees(VM.get_steer_from_curvature(curvature, v_ego, roll))

      actuators.torque = -steer_input
      actuators.curvature = curvature
      actuators.steeringAngleDeg = -angle

      prev_curvature = curvature
    else:
      prev_curvature = 0.0

    pm.send('carControl', cc_msg)

    cs_msg = messaging.new_message('controlsState')
    cs_msg.valid = True
    controlsState = cs_msg.controlsState
    controlsState.lateralControlState.init('debugState')

    lp = sm['liveParameters']
    steer_angle_without_offset = math.radians(sm['carState'].steeringAngleDeg - lp.angleOffsetDeg)
    controlsState.curvature = -VM.calc_curvature(steer_angle_without_offset, sm['carState'].vEgo, lp.roll)

    pm.send('controlsState', cs_msg)

    rk.keep_time()


def main():
  joystickd_thread()


if __name__ == "__main__":
  main()
