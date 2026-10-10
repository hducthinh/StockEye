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
