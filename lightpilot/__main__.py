"""LightPilot entry point: python -m lightpilot

Launches the GUI application.  Pass a file path to open it directly:
    python -m lightpilot photo.ARW
"""

import sys


def main() -> None:
    from .gui.app import run_gui
    run_gui()


if __name__ == "__main__":
    main()
