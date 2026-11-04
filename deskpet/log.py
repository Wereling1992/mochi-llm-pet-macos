"""Minimal log shim for deskpet body/brain (no full app logging required)."""
from __future__ import annotations

import logging

def setup() -> None:
    logging.basicConfig(level=logging.INFO)

def get(name: str):
    return logging.getLogger(f"deskpet.{name}")

def friendly(msg: str) -> None:
    print(msg)
