"""Lazy, path-independent access to the MP1 streaming predictor.

The MP1 source and trained model are mounted at /app/mp1-simulator in Docker.
For local development they live in the repository sibling directory
<repository>/projects/mp1/simulator. Importing this module does not load ML dependencies;
they are loaded only when the first complete sensor message is processed.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any


class MP1Predictor:
    """Small adapter around ``mp1-simulator/src/inference.py::Predictor``."""

    def __init__(self) -> None:
        module_root = self._resolve_module_root()
        module_root_str = str(module_root)
        if module_root_str not in sys.path:
            sys.path.insert(0, module_root_str)

        try:
            inference_module = importlib.import_module("src.inference")
            self._predictor = inference_module.Predictor()
        except Exception as exc:
            raise RuntimeError(
                "Unable to initialize the MP1 ML predictor. Verify that "
                "mp1-simulator is mounted and its requirements are installed."
            ) from exc

    @staticmethod
    def _resolve_module_root() -> Path:
        here = Path(__file__).resolve()
        # Docker mounts MP1 at /app/mp1-simulator; locally it is projects/mp1/simulator.
        candidates = (
            here.parents[2] / "mp1-simulator",  # Docker mount
            here.parents[3] / "mp1" / "simulator",  # consolidated repository layout
            here.parents[4] / "mp1-simulator",  # legacy layout fallback
        )
        for candidate in candidates:
            if (candidate / "src" / "inference.py").is_file() and (
                candidate / "models" / "mp1_model.joblib"
            ).is_file():
                return candidate
        expected = " or ".join(str(path) for path in candidates)
        raise FileNotFoundError(
            f"MP1 source/model not found. Expected mp1-simulator at: {expected}"
        )

    def predict(self, sensor_payload: dict[str, Any]) -> dict[str, Any]:
        return self._predictor.predict(sensor_payload)
