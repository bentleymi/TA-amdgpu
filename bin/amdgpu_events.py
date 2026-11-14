#!/usr/bin/env python3
"""Emit one JSON event per cycle with AMD GPU status."""
import sys

from amdgpu_common import discover, emit


def main():
    try:
        data = discover()
    except Exception:
        emit({"status": "absent", "gpu_count": 0, "kfd": 0, "cards": {}})
        return 0
    emit(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
