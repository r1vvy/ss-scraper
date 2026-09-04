import json
from pathlib import Path

from config import CONFIG_PATH, load_districts, normalize_districts, save_districts


def test_local_paths_use_project_root_abstraction():
    assert isinstance(CONFIG_PATH, Path)
    assert CONFIG_PATH == Path(__file__).resolve().parents[1] / "districts.json"


def test_normalize_districts_accepts_multiple_formats():
    assert normalize_districts("Centre,  mezciems, teika") == [
        "centre",
        "mezhciems",
        "teika",
    ]
    assert normalize_districts(["Centre", " centre ", "mezciems"]) == [
        "centre",
        "mezhciems",
    ]
    assert normalize_districts("centre mezaparks agenskalns jugla") == [
        "centre",
        "mezhapark",
        "agenskalns",
        "yugla",
    ]
    assert normalize_districts("centre-mezaparks-agenskalns-jugla") == [
        "centre",
        "mezhapark",
        "agenskalns",
        "yugla",
    ]


def test_normalize_districts_latvian_and_aliases():
    from config import normalize_district_name

    assert normalize_district_name("Āgenskalns") == "agenskalns"
    assert normalize_district_name("Pļavnieki") == "plyavnieki"
    assert normalize_district_name("Čiekurkalns") == "chiekurkalns"
    assert normalize_district_name("Mežciems") == "mezhciems"
    assert normalize_district_name("Torņakalns") == "tornjakalns"
    assert normalize_district_name("Vecrīga") == "vecriga"
    assert normalize_district_name("Zolitūde") == "zolitude"
    assert normalize_district_name("Iļģuciems") == "ilguciems"
    assert normalize_district_name("Centrs") == "centre"
    assert normalize_district_name("Center") == "centre"
    assert normalize_district_name("Chiekurkalns") == "chiekurkalns"

    assert normalize_districts("Āgenskalns, Pļavnieki, Purvciems, Centrs") == [
        "agenskalns",
        "plyavnieki",
        "purvciems",
        "centre",
    ]




def test_save_districts_persists_and_loads_from_file(tmp_path, monkeypatch):
    config_path = tmp_path / "districts.json"
    monkeypatch.setattr("config.CONFIG_PATH", config_path)

    districts = save_districts(["centre", "mezciems", "vecriga"])

    assert districts == ["centre", "mezhciems", "vecriga"]
    saved = json.loads(config_path.read_text())
    assert saved["districts"] == ["centre", "mezhciems", "vecriga"]
    assert load_districts() == ["centre", "mezhciems", "vecriga"]


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
