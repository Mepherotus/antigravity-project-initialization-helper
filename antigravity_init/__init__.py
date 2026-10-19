"""Antigravity Project Initialization Helper.

Zero-dependency setup and health audit tool for Antigravity workspaces.
"""

from pathlib import Path

__version__ = "0.1.0"
PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"

__all__ = ["__version__", "PACKAGE_DIR", "TEMPLATES_DIR"]
