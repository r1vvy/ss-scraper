import json
from pathlib import Path

from config import CONFIG_PATH, load_districts, normalize_districts, save_districts


def test_local_paths_use_project_root_abstraction():
    assert isinstance(CONFIG_PATH, Path)
    assert CONFIG_PATH == Path(__file__).resolve().parents[1] / "districts.json"


def test_normalize_districts_accepts_multiple_formats():
    assert normalize_districts("Centre,  mezciems, teika") == [
        "centre",
        "mezciems",
        "teika",
    ]
    assert normalize_districts(["Centre", " centre ", "mezciems"]) == [
        "centre",
        "mezciems",
    ]
    assert normalize_districts("centre mezaparks agenskalns jugla") == [
        "centre",
        "mezaparks",
        "agenskalns",
        "jugla",
    ]
    assert normalize_districts("centre-mezaparks-agenskalns-jugla") == [
        "centre",
        "mezaparks",
        "agenskalns",
        "jugla",
    ]



def test_save_districts_persists_and_loads_from_file(tmp_path, monkeypatch):
    config_path = tmp_path / "districts.json"
    monkeypatch.setattr("config.CONFIG_PATH", config_path)

    districts = save_districts(["centre", "mezciems", "old-town"])

    assert districts == ["centre", "mezciems", "old-town"]
    saved = json.loads(config_path.read_text())
    assert saved["districts"] == ["centre", "mezciems", "old-town"]
    assert load_districts() == ["centre", "mezciems", "old-town"]


def test_resolve_db_url_substitutes_and_encodes_password():
    from config import resolve_db_url

    raw = "postgresql://postgres:[YOUR-PASSWORD]@db.wgaziexghcbgvdrzgrxv.supabase.co:5432/postgres "
    resolved = resolve_db_url(raw, "p@ss:word#123")
    assert resolved == "postgresql://postgres:p%40ss%3Aword%23123@db.wgaziexghcbgvdrzgrxv.supabase.co:5432/postgres"

    # Direct URL with raw unencoded special characters in password
    unencoded_url = "postgresql://postgres:p@ss:w#rd/123@db.supabase.co:5432/postgres"
    resolved_unencoded = resolve_db_url(unencoded_url)
    assert resolved_unencoded == "postgresql://postgres:p%40ss%3Aw%23rd%2F123@db.supabase.co:5432/postgres"

    # With normal simple password
    direct = "postgresql://user:pass@localhost:5432/test"
    assert resolve_db_url(direct) == direct

    # Empty
    assert resolve_db_url("") is None
