from PyQt5.QtWidgets import QApplication

import ui.control_panel as control_panel_module
from ui.control_panel import ControlPanelUI


def test_detected_side_updates_orientation_and_turn(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(control_panel_module, "save_config", lambda config: dict(config))
    config = {
        "board_orientation": "white",
        "selected_side": "white",
        "engine_time_ms": 20,
        "multipv": 3,
    }
    panel = ControlPanelUI(config)
    panel.apply_detected_side("black")
    app.processEvents()

    assert panel.orientation.currentData() == "black"
    assert panel.selected_side.currentData() == "black"
    assert panel.config["board_orientation"] == "black"
    assert panel.config["selected_side"] == "black"
    panel.close()


def test_suggest_for_setting_saves_and_emits(monkeypatch):
    app = QApplication.instance() or QApplication([])
    saved_records = []
    monkeypatch.setattr(control_panel_module, "save_config", lambda cfg: dict(cfg))
    config = {
        "board_orientation": "black",
        "selected_side": "black",
        "engine_time_ms": 20,
        "multipv": 3,
        "suggest_for": "mine",
    }
    panel = ControlPanelUI(config)
    emitted = []
    panel.settings_changed.connect(lambda cfg: emitted.append(cfg))

    idx = panel.suggest_for.findData("both")
    panel.suggest_for.setCurrentIndex(idx)
    app.processEvents()

    assert panel.suggest_for.currentData() == "both"
    assert panel.config["suggest_for"] == "both"
    assert len(emitted) > 0
    assert emitted[-1]["suggest_for"] == "both"
    panel.close()


def test_preset_switching_updates_bbox_and_emits(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(control_panel_module, "save_config", lambda cfg: dict(cfg))
    config = {
        "board_orientation": "white",
        "selected_side": "white",
        "engine_time_ms": 20,
        "multipv": 3,
        "suggest_for": "mine",
        "active_preset": "standard",
        "board_presets": {
            "standard": {"name": "Bàn cờ thông thường", "bbox": {"left": 10, "top": 10, "width": 400, "height": 400}},
            "puzzle": {"name": "Puzzle Rush", "bbox": {"left": 500, "top": 50, "width": 300, "height": 300}},
        },
        "bbox": {"left": 10, "top": 10, "width": 400, "height": 400},
    }
    panel = ControlPanelUI(config)
    emitted = []
    panel.settings_changed.connect(lambda cfg: emitted.append(cfg))

    idx = panel.board_preset.findData("puzzle")
    panel.board_preset.setCurrentIndex(idx)
    app.processEvents()

    assert panel.board_preset.currentData() == "puzzle"
    assert panel.config["active_preset"] == "puzzle"
    assert panel.config["bbox"] == {"left": 500, "top": 50, "width": 300, "height": 300}
    assert len(emitted) > 0
    assert emitted[-1]["active_preset"] == "puzzle"
    assert emitted[-1]["bbox"]["left"] == 500
    panel.close()


def test_preset_quick_buttons_and_switch_preset(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(control_panel_module, "save_config", lambda cfg: dict(cfg))
    config = {
        "board_orientation": "white",
        "selected_side": "white",
        "engine_time_ms": 20,
        "multipv": 3,
        "suggest_for": "mine",
        "active_preset": "standard",
        "board_presets": {
            "standard": {"name": "Bàn cờ thông thường", "bbox": {"left": 10, "top": 10, "width": 400, "height": 400}},
            "puzzle": {"name": "Puzzle Rush", "bbox": {"left": 500, "top": 50, "width": 300, "height": 300}},
        },
        "bbox": {"left": 10, "top": 10, "width": 400, "height": 400},
    }
    panel = ControlPanelUI(config)
    resync_events = []
    panel.resync_requested.connect(lambda: resync_events.append(True))

    # Test button [6] / switch_preset("puzzle")
    panel.btn_preset_puzzle.click()
    app.processEvents()
    assert panel.config["active_preset"] == "puzzle"
    assert panel.board_preset.currentData() == "puzzle"
    assert panel.config["bbox"]["left"] == 500
    assert len(resync_events) == 1

    # Test button [5] / switch_preset("standard")
    panel.btn_preset_standard.click()
    app.processEvents()
    assert panel.config["active_preset"] == "standard"
    assert panel.board_preset.currentData() == "standard"
    assert panel.config["bbox"]["left"] == 10
    assert len(resync_events) == 2

    # Test trigger_resync (Hot key 3)
    panel.trigger_resync()
    app.processEvents()
    assert len(resync_events) == 3

    # Test toggle_pause (Hot key 4)
    pause_events = []
    panel.pause_changed.connect(lambda paused: pause_events.append(paused))
    assert panel.paused is False
    panel.toggle_pause()
    app.processEvents()
    assert panel.paused is True
    assert pause_events[-1] is True
    assert "TIẾP TỤC" in panel.pause_button.text()

    panel.toggle_pause()
    app.processEvents()
    assert panel.paused is False
    assert pause_events[-1] is False
    assert "TẠM DỪNG" in panel.pause_button.text()

    # Test toggle_visibility (Hot key 7)
    panel.show()
    app.processEvents()
    assert panel.isVisible() is True
    panel.toggle_visibility()
    app.processEvents()
    assert panel.isVisible() is False
    panel.toggle_visibility()
    app.processEvents()
    assert panel.isVisible() is True

    panel.close()
