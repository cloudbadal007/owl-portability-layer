"""Pytest fixtures: ontology paths."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def ontology_path() -> Path:
    return ROOT / "ontologies" / "procurement.ttl"


@pytest.fixture
def shacl_path() -> Path:
    return ROOT / "ontologies" / "procurement_shacl.ttl"
