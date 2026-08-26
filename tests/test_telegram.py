from unittest.mock import MagicMock

import main
from telegram import handle_district_command, handle_telegram_update


def test_handle_district_command_districts_view(tmp_path, monkeypatch):
    config_path = tmp_path / "districts.json"
    monkeypatch.setattr("config.CONFIG_PATH", config_path)
    monkeypatch.setattr("telegram.load_districts", lambda: ["centre", "mezciems"])

    result = handle_district_command("/districts")
    assert "centre, mezciems" in result


def test_handle_district_command_districts_update(tmp_path, monkeypatch):
    config_path = tmp_path / "districts.json"
    monkeypatch.setattr("config.CONFIG_PATH", config_path)

    result = handle_district_command("/districts agenskalns, teika")
    assert "agenskalns, teika" in result


def test_handle_district_command_reset(tmp_path, monkeypatch):
    config_path = tmp_path / "districts.json"
    monkeypatch.setattr("config.CONFIG_PATH", config_path)

    result = handle_district_command("/reset_districts")
    assert "centre" in result


def test_handle_district_command_help():
    result = handle_district_command("/help")
    assert "/scrape" in result
    assert "/districts" in result

    start_result = handle_district_command("/start")
    assert start_result == result


def test_handle_district_command_scrape_trigger(monkeypatch):
    mock_trigger = MagicMock(return_value=(True, "🚀 Scrape started"))
    monkeypatch.setattr("main.trigger_scrape", mock_trigger)

    result = handle_district_command("/scrape", chat_id="12345")
    assert result == "🚀 Scrape started"
    mock_trigger.assert_called_once_with(chat_id="12345")


def test_handle_district_command_with_bot_username(monkeypatch):
    mock_trigger = MagicMock(return_value=(True, "🚀 Scrape started"))
    monkeypatch.setattr("main.trigger_scrape", mock_trigger)

    result = handle_district_command("/scrape@my_bot", chat_id="12345")
    assert result == "🚀 Scrape started"
    mock_trigger.assert_called_once_with(chat_id="12345")


def test_handle_telegram_update_processes_slash_command(monkeypatch):
    mock_trigger = MagicMock(return_value=(True, "🚀 Scrape started"))
    monkeypatch.setattr("main.trigger_scrape", mock_trigger)

    update = {
        "message": {
            "text": "/scrape",
            "chat": {"id": 999},
        }
    }
    response = handle_telegram_update(update)
    assert response == {"chat_id": 999, "text": "🚀 Scrape started"}


def test_trigger_scrape_prevents_concurrent_runs(monkeypatch):
    monkeypatch.setattr("main.run_scraper", lambda notify_chat_id=None: (0, []))
    monkeypatch.setattr("main.load_districts", lambda: ["centre"])

    main._scrape_lock.acquire()
    try:
        started, msg = main.trigger_scrape(chat_id=123)
        assert started is False
        assert "already in progress" in msg
    finally:
        main._scrape_lock.release()


def test_send_telegram_message_retries_on_429(monkeypatch):
    from telegram import send_telegram_message

    monkeypatch.setattr("telegram.TELEGRAM_BOT_TOKEN", "12345:dummytoken")
    monkeypatch.setattr("telegram.TELEGRAM_CHAT_ID", "99999")
    monkeypatch.setattr("time.sleep", lambda secs: None)

    response_429 = MagicMock()
    response_429.status_code = 429
    response_429.json.return_value = {"ok": False, "error_code": 429, "parameters": {"retry_after": 2}}

    response_200 = MagicMock()
    response_200.status_code = 200
    response_200.raise_for_status.return_value = None

    mock_post = MagicMock(side_effect=[response_429, response_200])
    monkeypatch.setattr("requests.post", mock_post)

    success = send_telegram_message("Test message", chat_id="99999")
    assert success is True
    assert mock_post.call_count == 2

