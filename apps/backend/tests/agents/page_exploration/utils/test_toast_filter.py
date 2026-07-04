from app.agents.page_exploration.utils.toast_filter import is_toast, filter_snapshot


def test_is_toast_role_status():
    info = {"role": "status", "aria_modal": None, "timeout_ms": 3000}
    assert is_toast(info) is True


def test_is_toast_role_alert_short_timeout():
    info = {"role": "alert", "aria_modal": None, "timeout_ms": 3000}
    assert is_toast(info) is True


def test_dialog_not_toast():
    info = {"role": "dialog", "aria_modal": True, "timeout_ms": 3000}
    assert is_toast(info) is False


def test_alert_without_timeout_not_toast():
    # 长 timeout 或未知 -> 不当 toast
    info = {"role": "alert", "aria_modal": None, "timeout_ms": None}
    assert is_toast(info) is False


def test_known_ant_message_container():
    info = {"role": "status", "aria_modal": None, "timeout_ms": 3000,
            "dom_path": "div#root > .ant-message"}
    assert is_toast(info) is True


def test_filter_snapshot_drops_toasts():
    snap = [
        {"role": "button", "aria_modal": None, "timeout_ms": None},   # keep
        {"role": "status", "aria_modal": None, "timeout_ms": 3000},  # drop
        {"role": "dialog", "aria_modal": True, "timeout_ms": None},  # keep
        {"role": "alert", "aria_modal": None, "timeout_ms": 4000},   # drop
    ]
    out = filter_snapshot(snap)
    assert len(out) == 2
    assert out[0]["role"] == "button"
    assert out[1]["role"] == "dialog"
