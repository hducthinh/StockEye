import json
import os
import sys
from copy import deepcopy
from pathlib import Path


SCHEMA_VERSION = 2

DEFAULT_CONFIG = {
    "schema_version": SCHEMA_VERSION,
    "bbox": None,
    "board_presets": {
        "standard": {
            "name": "Bàn cờ thông thường",
            "bbox": None,
        },
        "puzzle": {
            "name": "Puzzle Rush",
            "bbox": None,
        },
    },
    "active_preset": "standard",
    "board_orientation": "white",
    "selected_side": "white",
    "capture_fps": 60,
    "pixel_diff_threshold": 35,
    "square_change_threshold": 0.08,
    "recognition_threshold": 0.65,
    "recognition_margin": 0.01,
    "engine_time_ms": 20,
    "threads": 1,
    "multipv": 3,
    "draw_on_main_board": True,
    "suggest_for": "mine",
}


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def config_path() -> Path:
    return app_dir() / "config.json"


def templates_dir(preset: str = "standard") -> Path:
    preset_key = str(preset or "standard").lower()
    sub = app_dir() / "templates" / preset_key
    if sub.exists() and any(sub.glob("*.png")):
        return sub
    return app_dir() / "templates"


def preset_templates_dir(preset: str = "standard") -> Path:
    preset_key = str(preset or "standard").lower()
    return app_dir() / "templates" / preset_key


def engine_path() -> Path:
    target = app_dir() / "engine" / "stockfish19.exe"
    if target.exists():
        return target
    engine_dir = app_dir() / "engine"
    if engine_dir.exists():
        for exe in engine_dir.glob("*.exe"):
            return exe
    return target


def _migrate(raw: dict) -> dict:
    cfg = deepcopy(DEFAULT_CONFIG)
    raw_presets = raw.get("board_presets")
    if isinstance(raw_presets, dict):
        for k in ("standard", "puzzle"):
            if k in raw_presets and isinstance(raw_presets[k], dict):
                cfg["board_presets"][k]["bbox"] = raw_presets[k].get("bbox")
                if "name" in raw_presets[k]:
                    cfg["board_presets"][k]["name"] = str(raw_presets[k]["name"])

    if cfg["board_presets"]["standard"]["bbox"] is None and raw.get("bbox"):
        cfg["board_presets"]["standard"]["bbox"] = raw.get("bbox")

    active = str(raw.get("active_preset", "standard")).lower()
    if active not in cfg["board_presets"]:
        active = "standard"
    cfg["active_preset"] = active
    cfg["bbox"] = cfg["board_presets"][active]["bbox"] or raw.get("bbox")

    legacy_side = str(raw.get("force_side", raw.get("player_color", "white"))).lower()
    if legacy_side not in {"white", "black"}:
        legacy_side = "white"
    cfg["board_orientation"] = str(raw.get("board_orientation", raw.get("player_color", legacy_side))).lower()
    if cfg["board_orientation"] not in {"white", "black"}:
        cfg["board_orientation"] = legacy_side
    cfg["selected_side"] = str(raw.get("selected_side", legacy_side)).lower()
    if cfg["selected_side"] not in {"white", "black"}:
        cfg["selected_side"] = "white"
    cfg["threads"] = max(1, min(32, int(raw.get("threads", 1))))
    cfg["multipv"] = max(1, min(4, int(raw.get("multipv", 3))))
    if "engine_time_ms" in raw:
        time_ms = int(raw["engine_time_ms"])
    else:
        # Legacy presets used 100–250 ms. V2 intentionally targets a sub-100 ms pipeline.
        time_ms = min(20, round(float(raw.get("time_limit", 0.02)) * 1000))
    cfg["engine_time_ms"] = max(10, min(50, time_ms))
    cfg["draw_on_main_board"] = bool(raw.get("draw_on_main_board", True))
    for key in (
        "capture_fps", "pixel_diff_threshold", "square_change_threshold",
        "recognition_threshold", "recognition_margin",
    ):
        if key in raw:
            cfg[key] = raw[key]
    return cfg


def validate_config(cfg: dict) -> dict:
    result = deepcopy(DEFAULT_CONFIG)
    result.update(cfg)
    result["schema_version"] = SCHEMA_VERSION
    result["capture_fps"] = max(10, min(120, int(result["capture_fps"])))
    result["pixel_diff_threshold"] = max(5, min(100, int(result["pixel_diff_threshold"])))
    result["square_change_threshold"] = max(0.01, min(0.8, float(result["square_change_threshold"])))
    result["recognition_threshold"] = max(0.1, min(0.99, float(result["recognition_threshold"])))
    result["recognition_margin"] = max(0.0, min(0.5, float(result["recognition_margin"])))
    result["engine_time_ms"] = max(10, min(50, int(result["engine_time_ms"])))
    result["threads"] = max(1, min(32, int(result["threads"])))
    result["multipv"] = max(1, min(4, int(result["multipv"])))
    for key in ("board_orientation", "selected_side"):
        if result[key] not in {"white", "black"}:
            result[key] = "white"
    if result.get("suggest_for") not in {"mine", "both", "white", "black"}:
        result["suggest_for"] = "mine"
    required = {"left", "top", "width", "height"}
    presets = deepcopy(DEFAULT_CONFIG["board_presets"])
    raw_presets = cfg.get("board_presets")
    if isinstance(raw_presets, dict):
        for k in ("standard", "puzzle"):
            if k in raw_presets and isinstance(raw_presets[k], dict):
                p_bbox = raw_presets[k].get("bbox")
                if (
                    p_bbox is not None
                    and isinstance(p_bbox, dict)
                    and required.issubset(p_bbox)
                    and p_bbox["width"] > 0
                    and p_bbox["height"] > 0
                ):
                    presets[k]["bbox"] = {
                        "left": int(p_bbox["left"]),
                        "top": int(p_bbox["top"]),
                        "width": int(p_bbox["width"]),
                        "height": int(p_bbox["height"]),
                    }
                if "name" in raw_presets[k]:
                    presets[k]["name"] = str(raw_presets[k]["name"])

    raw_bbox = cfg.get("bbox")
    if (
        presets["standard"]["bbox"] is None
        and raw_bbox is not None
        and isinstance(raw_bbox, dict)
        and required.issubset(raw_bbox)
        and raw_bbox["width"] > 0
        and raw_bbox["height"] > 0
    ):
        presets["standard"]["bbox"] = {
            "left": int(raw_bbox["left"]),
            "top": int(raw_bbox["top"]),
            "width": int(raw_bbox["width"]),
            "height": int(raw_bbox["height"]),
        }

    active = str(cfg.get("active_preset", "standard")).lower()
    if active not in presets:
        active = "standard"
    result["board_presets"] = presets
    result["active_preset"] = active

    active_bbox = presets[active]["bbox"]
    if active_bbox is not None:
        result["bbox"] = active_bbox
    elif (
        raw_bbox is not None
        and isinstance(raw_bbox, dict)
        and required.issubset(raw_bbox)
        and raw_bbox["width"] > 0
        and raw_bbox["height"] > 0
    ):
        result["bbox"] = {
            "left": int(raw_bbox["left"]),
            "top": int(raw_bbox["top"]),
            "width": int(raw_bbox["width"]),
            "height": int(raw_bbox["height"]),
        }
    else:
        result["bbox"] = None
    return result


def load_config(path: Path | None = None) -> dict:
    path = path or config_path()
    raw = {}
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
    if raw.get("schema_version") == SCHEMA_VERSION:
        cfg = deepcopy(DEFAULT_CONFIG)
        cfg.update(raw)
    else:
        cfg = _migrate(raw)
    return validate_config(cfg)


def save_config(cfg: dict, path: Path | None = None) -> dict:
    path = path or config_path()
    clean = validate_config(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(clean, indent=4, ensure_ascii=False), encoding="utf-8")
    os.replace(temp_path, path)
    return clean
