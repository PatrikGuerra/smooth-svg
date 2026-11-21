"""Frozen entry point: no CLI, goes straight to app mode."""
import sys

from smoothsvg.app import run

if __name__ == "__main__":
    sys.exit(run())
