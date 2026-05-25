# backend/tests/conftest.py
import pytest
from pathlib import Path


@pytest.fixture
def tmp_data_dir(tmp_path):
    return tmp_path
