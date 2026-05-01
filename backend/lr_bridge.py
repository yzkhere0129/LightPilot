"""
File-system IPC bridge between Python backend and LR Classic Lua plugin.

Directory layout (~/.lightpilot/):
  current_settings.json  — Lua writes current develop params here
  current_preview.jpg    — Lua exports small JPEG preview here
  pending_update.json    — Python writes new params here; Lua detects and applies
  status.txt             — State machine: idle / exporting / ready / applying / done / error
  log.txt                — Append-only event log
"""

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class BridgeError(Exception):
    pass


class LRBridge:
    STATUS_IDLE = "idle"
    STATUS_EXPORTING = "exporting"
    STATUS_READY = "ready"
    STATUS_APPLYING = "applying"
    STATUS_DONE = "done"
    STATUS_ERROR = "error"
    STATUS_SCAN_HISTORY = "scan_history"
    STATUS_SCAN_SELECTED = "scan_selected"
    STATUS_SCAN_DONE = "scan_done"
    STATUS_EXPORT_THUMBS = "export_thumbs"
    STATUS_THUMBS_DONE = "thumbs_done"

    def __init__(self, bridge_dir: str | Path, poll_interval: float = 0.5, timeout: float = 30.0):
        self.bridge_dir = Path(bridge_dir).expanduser()
        self.bridge_dir.mkdir(parents=True, exist_ok=True)
        self.poll_interval = poll_interval
        self.timeout = timeout

        self._settings_path = self.bridge_dir / "current_settings.json"
        self._preview_path = self.bridge_dir / "current_preview.jpg"
        self._pending_path = self.bridge_dir / "pending_update.json"
        self._status_path = self.bridge_dir / "status.txt"
        self._log_path = self.bridge_dir / "log.txt"

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def _read_status(self) -> str:
        try:
            return self._status_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return self.STATUS_IDLE

    def _write_status(self, status: str) -> None:
        self._status_path.write_text(status, encoding="utf-8")

    def _append_log(self, msg: str) -> None:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")

    def _wait_for_status(self, target: str, error_ok: bool = False) -> str:
        """Poll until status reaches target (or error). Returns final status."""
        deadline = time.time() + self.timeout
        printed_waiting = False
        while time.time() < deadline:
            status = self._read_status()
            if status == target:
                return status
            if status == self.STATUS_ERROR and not error_ok:
                raise BridgeError(f"LR plugin reported error while waiting for '{target}'")
            if not printed_waiting:
                remaining = int(deadline - time.time())
                print(f"  [LightPilot] Waiting for LR plugin (status: {status} → {target}, timeout: {remaining}s)...")
                print(f"               Make sure LR is open and 'LightPilot — Start Session' is running.")
                printed_waiting = True
            time.sleep(self.poll_interval)
        raise BridgeError(
            f"Timeout ({self.timeout}s) waiting for LR status '{target}', "
            f"last status: {self._read_status()}"
        )

    # ------------------------------------------------------------------
    # High-level API
    # ------------------------------------------------------------------

    def request_export(self) -> tuple[dict, Path]:
        """
        Tell LR to export current settings + preview.
        Returns (settings_dict, preview_path) when ready.
        """
        self._append_log("Python → requesting export")
        self._write_status(self.STATUS_EXPORTING)

        self._wait_for_status(self.STATUS_READY)
        self._append_log("LR → export ready")

        settings = json.loads(self._settings_path.read_text(encoding="utf-8"))

        # Try LR-exported preview first
        tmp_preview = self.bridge_dir / "preview_snapshot.jpg"
        if self._preview_path.exists() and self._preview_path.stat().st_size > 1000:
            shutil.copy2(self._preview_path, tmp_preview)
        else:
            # Fallback: read source photo path written by Lua
            photo_path_file = self.bridge_dir / "current_photo_path.txt"
            if photo_path_file.exists():
                src = Path(photo_path_file.read_text(encoding="utf-8").strip())
                if src.exists():
                    # If it's a JPEG, use directly; otherwise Python needs rawpy
                    if src.suffix.lower() in (".jpg", ".jpeg", ".png", ".tif", ".tiff"):
                        shutil.copy2(src, tmp_preview)
                        self._append_log(f"Using source file as preview: {src.name}")
                    else:
                        # RAW file — try to convert with Pillow or just use it
                        shutil.copy2(src, tmp_preview)
                        self._append_log(f"Source is RAW ({src.suffix}), copied as-is")

        return settings, tmp_preview

    def send_adjustments(self, adjustments: dict) -> None:
        """
        Write new parameter deltas for LR to apply.
        Blocks until LR confirms application.
        """
        self._append_log(f"Python → sending adjustments: {list(adjustments.keys())}")
        self._pending_path.write_text(
            json.dumps({"adjustments": adjustments, "mode": "delta"}, indent=2),
            encoding="utf-8",
        )
        self._write_status(self.STATUS_APPLYING)

        self._wait_for_status(self.STATUS_DONE)
        self._append_log("LR → adjustments applied")
        self._write_status(self.STATUS_IDLE)

    def get_current_settings(self) -> Optional[dict]:
        """Read the last exported settings without triggering a new export."""
        try:
            return json.loads(self._settings_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def is_lr_running(self) -> bool:
        """Heuristic check: LR plugin updates a heartbeat timestamp."""
        heartbeat = self.bridge_dir / "heartbeat.txt"
        if not heartbeat.exists():
            return False
        try:
            ts = float(heartbeat.read_text().strip())
            return (time.time() - ts) < 10.0  # within 10 seconds
        except ValueError:
            return False

    def reset(self) -> None:
        """Clear pending state, useful before starting a new session."""
        self._write_status(self.STATUS_IDLE)
        if self._pending_path.exists():
            self._pending_path.unlink()
        self._append_log("Python → bridge reset")
