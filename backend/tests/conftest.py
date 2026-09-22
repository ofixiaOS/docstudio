from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest


_SYSTEM_TEMP = Path(tempfile.gettempdir()).resolve()
_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="docstudio-tests-", dir=_SYSTEM_TEMP)).resolve()

# Pytest imports this file before collecting test modules. These variables must
# therefore be set here, before importing main creates its module-level Store.
os.environ["GAMMA_DATA_DIR"] = str(_TEST_DATA_DIR)
os.environ["GEMINI_API_KEY"] = ""


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    return _TEST_DATA_DIR


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    del session, exitstatus
    if _TEST_DATA_DIR.parent != _SYSTEM_TEMP or not _TEST_DATA_DIR.name.startswith("docstudio-tests-"):
        raise RuntimeError(f"Directorio temporal de pruebas inesperado: {_TEST_DATA_DIR}")
    shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)
