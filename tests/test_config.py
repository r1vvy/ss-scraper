import json
from pathlib import Path

from config import CONFIG_PATH, DB_PATH, load_districts, normalize_districts, save_districts


def test_local_paths_use_project_root_abstraction():
    assert isinstance(CONFIG_PATH, Path)
    assert isinstance(DB_PATH, Path)
    assert CONFIG_PATH == Path(__file__).resolve().parents[1] / "districts.json"
    assert DB_PATH == Path(__file__).resolve().parents[1] / "ss_listings.db"


def test_normalize_districts_accepts_multiple_formats():
    assert normalize_districts("Centre,  mezciems, old-town") == [
        "centre",
        "mezciems",
        "old-town",
    ]
    assert normalize_districts(["Centre", " centre ", "mezciems"]) == [
        "centre",
        "mezciems",
    ]


def test_save_districts_persists_and_loads_from_file(tmp_path, monkeypatch):
    config_path = tmp_path / "districts.json"
    monkeypatch.setattr("config.CONFIG_PATH", str(config_path))

    districts = save_districts(["centre", "mezciems", "old-town"])

    assert districts == ["centre", "mezciems", "old-town"]
    saved = json.loads(config_path.read_text())
    assert saved["districts"] == ["centre", "mezciems", "old-town"]
    assert load_districts() == ["centre", "mezciems", "old-town"]
