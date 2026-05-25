# backend/tests/conftest.py
import pytest


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("config.settings.data_dir", tmp_path)
    return tmp_path
