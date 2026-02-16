#!/usr/bin/env python3
import os
import pyray as rl

from openpilot.system.hardware import TICI
from openpilot.common.realtime import config_realtime_process, set_core_affinity
from openpilot.system.ui.lib.application import gui_app
from openpilot.selfdrive.ui.layouts.main import MainLayout
from openpilot.selfdrive.ui.mici.layouts.main import MiciMainLayout
from openpilot.selfdrive.ui.ui_state import ui_state


def main():
  cores = {5, }
  config_realtime_process(0, 51)

  gui_app.init_window("UI")
  def _build_layout(big: bool):
    layout = MainLayout() if big else MiciMainLayout()
    layout.set_rect(rl.Rectangle(0, 0, gui_app.width, gui_app.height))
    return layout

  current_big_ui = gui_app.big_ui()
  main_layout = _build_layout(current_big_ui)
  for should_render in gui_app.render():
    ui_state.update()

    # Rebuild layout when the compact UI toggle changes while disengaged
    desired_big_ui = gui_app.big_ui()
    if not ui_state.engaged and desired_big_ui != current_big_ui:
      main_layout.hide_event()
      gui_app.resize_for_layout(desired_big_ui)
      main_layout = _build_layout(desired_big_ui)
      current_big_ui = desired_big_ui

    if should_render:
      main_layout.render()

      # reaffine after power save offlines our core
      if TICI and os.sched_getaffinity(0) != cores:
        try:
          set_core_affinity(list(cores))
        except OSError:
          pass


if __name__ == "__main__":
  main()
