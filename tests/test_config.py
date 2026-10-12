import json

from core.config import SCHEMA_VERSION, load_config, save_config


def test_legacy_config_is_migrated(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "bbox": {"left": 10, "top": 20, "width": 640, "height": 640},
        "player_color": "black",
        "force_side": "white",
        "time_limit": 0.1,
        "threads": 2,
        "engine_disguise_name": "chrome.exe",
    }), encoding="utf-8")
    config = load_config(path)
    assert config["schema_version"] == SCHEMA_VERSION
    assert config["board_orientation"] == "black"
    assert config["selected_side"] == "white"
    assert config["engine_time_ms"] == 20
    assert "engine_disguise_name" not in config


def test_save_is_validated_and_round_trips(tmp_path):
    path = tmp_path / "config.json"
    saved = save_config({"engine_time_ms": 1, "multipv": 99}, path)
    assert saved["engine_time_ms"] == 10
    assert saved["multipv"] == 4
    assert load_config(path) == saved


def test_board_presets_migrated_and_validated(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "bbox": {"left": 100, "top": 200, "width": 500, "height": 500},
    }), encoding="utf-8")
    cfg = load_config(path)
    assert cfg["active_preset"] == "standard"
    assert cfg["board_presets"]["standard"]["bbox"] == {"left": 100, "top": 200, "width": 500, "height": 500}
    assert cfg["board_presets"]["puzzle"]["bbox"] is None
    assert cfg["bbox"] == {"left": 100, "top": 200, "width": 500, "height": 500}

    # Save with puzzle preset active
    cfg["board_presets"]["puzzle"]["bbox"] = {"left": 400, "top": 150, "width": 450, "height": 450}
    cfg["active_preset"] = "puzzle"
    saved = save_config(cfg, path)
    assert saved["active_preset"] == "puzzle"
    assert saved["bbox"] == {"left": 400, "top": 150, "width": 450, "height": 450}
