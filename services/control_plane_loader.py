#!/usr/bin/env python3
"""兼容 `services/control-plane` 目录名的动态加载器。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def build_controller():
    control_plane_dir = Path(__file__).resolve().parent / "control-plane"
    controller_path = control_plane_dir / "controller.py"
    if str(control_plane_dir) not in sys.path:
        sys.path.insert(0, str(control_plane_dir))
    spec = importlib.util.spec_from_file_location("control_plane_controller", controller_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.ControlPlaneController()
