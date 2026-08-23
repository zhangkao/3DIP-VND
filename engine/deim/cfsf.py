"""
Thin wrapper around the repo-root `CFSF.py` so it can be imported reliably from
within the `engine.deim` package.
"""

from __future__ import annotations

from importlib import util as importlib_util
from pathlib import Path
from types import ModuleType
from typing import Tuple

__all__ = ["CFSFModule", "SpatialWeights", "ChannelWeights"]


def _load_cfsf() -> Tuple[type, type, type]:
    try:
        from CFSF import CFSFModule, SpatialWeights, ChannelWeights  # type: ignore

        return CFSFModule, SpatialWeights, ChannelWeights
    except Exception:
        repo_root = Path(__file__).resolve().parents[2]
        cfsf_path = repo_root / "CFSF.py"
        if not cfsf_path.exists():
            raise

        spec = importlib_util.spec_from_file_location("_deim_root_cfsf", str(cfsf_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Failed to load CFSF module from {cfsf_path}")
        module = importlib_util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[attr-defined]
        return module.CFSFModule, module.SpatialWeights, module.ChannelWeights


CFSFModule, SpatialWeights, ChannelWeights = _load_cfsf()

