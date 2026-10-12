from core.hotkey import GlobalHotkeyListener


def test_global_hotkey_listener_initialization_and_stop():
    listener = GlobalHotkeyListener()
    assert listener._running is True
    # Verify all 5 hotkey signals are present
    assert hasattr(listener, "resync_requested")
    assert hasattr(listener, "pause_toggled")
    assert hasattr(listener, "preset_requested")
    assert hasattr(listener, "toggle_visibility_requested")

    recorded = []
    listener.resync_requested.connect(lambda: recorded.append("resync"))
    listener.pause_toggled.connect(lambda: recorded.append("pause"))
    listener.preset_requested.connect(lambda p: recorded.append(p))
    listener.toggle_visibility_requested.connect(lambda: recorded.append("toggle_vis"))

    listener.resync_requested.emit()
    listener.pause_toggled.emit()
    listener.preset_requested.emit("standard")
    listener.toggle_visibility_requested.emit()
    assert recorded == ["resync", "pause", "standard", "toggle_vis"]

    listener.stop()
    assert listener._running is False
