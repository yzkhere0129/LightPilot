"""Sidecar JSON file management for non-destructive editing.

Each image gets a companion `.lightpilot.json` file that stores
all editing parameters.  The original file is never modified.

Example:
    photo.ARW  →  photo.ARW.lightpilot.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SIDECAR_SUFFIX = ".lightpilot.json"
SIDECAR_VERSION = 1


def sidecar_path(image_path: str | Path) -> Path:
    """Return the sidecar file path for a given image."""
    p = Path(image_path)
    return p.parent / (p.name + SIDECAR_SUFFIX)


def load(image_path: str | Path) -> dict[str, Any]:
    """Load editing parameters from sidecar.

    Returns empty dict if the sidecar doesn't exist yet.
    """
    sp = sidecar_path(image_path)
    if sp.exists():
        data = json.loads(sp.read_text(encoding="utf-8"))
        return data.get("params", data)  # handle both wrapped and flat
    return {}


def save(image_path: str | Path, params: dict[str, Any]) -> None:
    """Save editing parameters to sidecar (overwrites)."""
    sp = sidecar_path(image_path)
    payload = {
        "version": SIDECAR_VERSION,
        "source": str(Path(image_path).name),
        "params": params,
    }
    sp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def merge(image_path: str | Path, updates: dict[str, Any]) -> dict[str, Any]:
    """Load existing params, merge updates, save, and return the merged dict."""
    params = load(image_path)
    params.update(updates)
    save(image_path, params)
    return params
