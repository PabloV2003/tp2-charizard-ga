import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from charizard_ga.config import load_experiments  # noqa: E402
from charizard_ga.data import load_catalog  # noqa: E402


@pytest.fixture(scope="session")
def catalog():
    return load_catalog()


@pytest.fixture(scope="session")
def experiments():
    return load_experiments()


@pytest.fixture(scope="session")
def base_weights(experiments):
    return experiments["profiles"]["R1"]
