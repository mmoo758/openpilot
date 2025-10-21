"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
LIMIT_ADAPT_ACC = -1.  # m/s^2 Ideal acceleration for the adapting (braking) phase when approaching speed limits.
LIMIT_MAX_MAP_DATA_AGE = 10.  # s Maximum time to hold to map data, then consider it invalid inside limits controllers.

# Speed Limit Assist constants
# Mapping of (threshold speed in unit system, max PCM set speed in m/s) ordered by ascending thresholds.
PCM_LONG_REQUIRED_MAX_SET_SPEED = {
  True: (
    (20, 5.5555556),   # <= 20 km/h
    (30, 8.3333333),   # <= 30 km/h
    (40, 11.1111111),  # <= 40 km/h
    (50, 13.8888889),  # <= 50 km/h
    (60, 16.6666667),  # <= 60 km/h
    (70, 19.4444444),  # <= 70 km/h
    (80, 22.2222222),  # <= 80 km/h
    (90, 25.0),        # <= 90 km/h
    (100, 27.7777778), # <= 100 km/h
    (110, 30.5555556), # <= 110 km/h
    (120, 33.3333333), # <= 120 km/h
    (130, 36.1111111), # <= 130 km/h
  ),
  False: (
    (15, 6.7056),    # <= 15 mph
    (20, 8.9408),    # <= 20 mph
    (25, 11.176),    # <= 25 mph
    (30, 13.4112),   # <= 30 mph
    (35, 15.6464),   # <= 35 mph
    (40, 17.8816),   # <= 40 mph
    (45, 20.1168),   # <= 45 mph
    (50, 22.352),    # <= 50 mph
    (55, 24.5872),   # <= 55 mph
    (60, 26.8224),   # <= 60 mph
    (65, 29.0576),   # <= 65 mph
    (70, 31.2928),   # <= 70 mph
    (75, 33.528),    # <= 75 mph
    (80, 35.7632),   # <= 80 mph
    (85, 37.9984),   # <= 85 mph
    (90, 40.2336),   # <= 90 mph
  ),
}

CONFIRM_SPEED_THRESHOLD = {
  True: 80,   # km/h
  False: 50,  # mph
}


def resolve_pcm_long_required_max(metric: bool, limit_conv: int, has_speed_limit: bool) -> float:
  segments = PCM_LONG_REQUIRED_MAX_SET_SPEED[metric]

  if not has_speed_limit:
    return segments[-1][1]

  for threshold, value in segments:
    if limit_conv <= threshold:
      return value

  return segments[-1][1]
