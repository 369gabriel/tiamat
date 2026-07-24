import pytest

import RageQueue as ragequeue_module
from RageQueue import RageQueue


class FakeResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data


def test_ragequeue_starts_selected_queue_once_after_game():
    ragequeue = RageQueue(
        {"ragequeue": {"enabled": True, "queue_id": 450}}
    )
    phases = iter(["InProgress", "EndOfGame", "Lobby", "Lobby"])
    calls = []

    def fake_lcu_request(method, endpoint, body):
        calls.append((method, endpoint, body))
        if endpoint == "/lol-gameflow/v1/gameflow-phase":
            return FakeResponse(data=next(phases))
        return FakeResponse(status_code=204)

    ragequeue.rengar.lcu_request = fake_lcu_request

    ragequeue.check_gameflow()
    ragequeue.check_gameflow()
    ragequeue.check_gameflow()
    ragequeue.check_gameflow()

    assert calls == [
        ("GET", "/lol-gameflow/v1/gameflow-phase", ""),
        ("GET", "/lol-gameflow/v1/gameflow-phase", ""),
        ("POST", "/lol-lobby/v2/play-again", ""),
        ("GET", "/lol-gameflow/v1/gameflow-phase", ""),
        ("POST", "/lol-lobby/v2/lobby", {"queueId": 450}),
        ("POST", "/lol-lobby/v2/lobby/matchmaking/search", ""),
        ("GET", "/lol-gameflow/v1/gameflow-phase", ""),
    ]


def test_selecting_queue_enables_and_saves_ragequeue(monkeypatch):
    config = {"ragequeue": {"enabled": False, "queue_id": 420}}
    ragequeue = RageQueue(config)
    saved_configs = []
    monkeypatch.setattr(
        ragequeue_module,
        "save_config",
        lambda saved_config: saved_configs.append(saved_config.copy()),
    )

    ragequeue.set_queue(400)

    assert ragequeue.enabled is True
    assert ragequeue.queue_name == "Normal Draft Pick"
    assert config["ragequeue"] == {
        "enabled": True,
        "queue_id": 400,
        "first_position": None,
        "second_position": None,
    }
    assert saved_configs == [config]


@pytest.mark.parametrize(
    ("queue_id", "queue_name"),
    [
        (1090, "TFT Normal"),
        (1100, "TFT Ranked"),
        (1130, "TFT Hyper Roll"),
        (1160, "TFT Double Up"),
    ],
)
def test_tft_queue_modes_are_supported(queue_id, queue_name, monkeypatch):
    ragequeue = RageQueue(
        {"ragequeue": {"enabled": False, "queue_id": 420}}
    )
    monkeypatch.setattr(ragequeue_module, "save_config", lambda _config: None)

    ragequeue.set_queue(queue_id)

    assert ragequeue.queue_name == queue_name
    assert ragequeue.positions_name == "Not used"


def test_tft_queue_does_not_send_position_preferences():
    ragequeue = RageQueue(
        {
            "ragequeue": {
                "enabled": True,
                "queue_id": 1100,
                "first_position": "TOP",
                "second_position": "JUNGLE",
            }
        }
    )
    calls = []

    def fake_lcu_request(method, endpoint, body):
        calls.append((method, endpoint, body))
        return FakeResponse(status_code=200)

    ragequeue.rengar.lcu_request = fake_lcu_request
    ragequeue.start_queue()

    assert calls == [
        ("POST", "/lol-lobby/v2/lobby", {"queueId": 1100}),
        ("POST", "/lol-lobby/v2/lobby/matchmaking/search", ""),
    ]


def test_configure_saves_queue_and_both_positions(monkeypatch):
    config = {"ragequeue": {"enabled": False, "queue_id": 420}}
    ragequeue = RageQueue(config)
    monkeypatch.setattr(ragequeue_module, "save_config", lambda _config: None)

    ragequeue.configure(440, "MIDDLE", "BOTTOM")

    assert ragequeue.enabled is True
    assert ragequeue.positions_name == "Mid / Bottom"
    assert config["ragequeue"] == {
        "enabled": True,
        "queue_id": 440,
        "first_position": "MIDDLE",
        "second_position": "BOTTOM",
    }


def test_selecting_queue_starts_from_idle_client(monkeypatch):
    config = {"ragequeue": {"enabled": False, "queue_id": 420}}
    ragequeue = RageQueue(config)
    calls = []
    monkeypatch.setattr(ragequeue_module, "save_config", lambda _config: None)

    def fake_lcu_request(method, endpoint, body):
        calls.append((method, endpoint, body))
        if endpoint == "/lol-gameflow/v1/gameflow-phase":
            return FakeResponse(data="None")
        return FakeResponse(status_code=200)

    ragequeue.rengar.lcu_request = fake_lcu_request
    ragequeue.set_queue(400)
    ragequeue.check_gameflow()
    ragequeue.check_gameflow()

    assert calls == [
        ("GET", "/lol-gameflow/v1/gameflow-phase", ""),
        ("POST", "/lol-lobby/v2/lobby", {"queueId": 400}),
        ("POST", "/lol-lobby/v2/lobby/matchmaking/search", ""),
        ("GET", "/lol-gameflow/v1/gameflow-phase", ""),
    ]


def test_armed_ragequeue_starts_if_end_of_game_phase_is_skipped():
    ragequeue = RageQueue(
        {"ragequeue": {"enabled": True, "queue_id": 420}}
    )
    phases = iter(["InProgress", "Lobby"])
    calls = []

    def fake_lcu_request(method, endpoint, body):
        calls.append((method, endpoint, body))
        if endpoint == "/lol-gameflow/v1/gameflow-phase":
            return FakeResponse(data=next(phases))
        return FakeResponse(status_code=200)

    ragequeue.rengar.lcu_request = fake_lcu_request
    ragequeue.check_gameflow()
    ragequeue.check_gameflow()

    assert ("POST", "/lol-lobby/v2/lobby", {"queueId": 420}) in calls
    assert ("POST", "/lol-lobby/v2/lobby/matchmaking/search", "") in calls


def test_invalid_queue_is_rejected():
    ragequeue = RageQueue(
        {"ragequeue": {"enabled": False, "queue_id": 420}}
    )

    with pytest.raises(ValueError, match="Unsupported queue ID"):
        ragequeue.set_queue(999)


def test_matchmaking_does_not_start_when_lobby_creation_fails():
    ragequeue = RageQueue(
        {"ragequeue": {"enabled": True, "queue_id": 420}}
    )
    calls = []

    def fake_lcu_request(method, endpoint, body):
        calls.append((method, endpoint, body))
        return FakeResponse(status_code=500)

    ragequeue.rengar.lcu_request = fake_lcu_request

    with pytest.raises(RuntimeError, match="create the lobby"):
        ragequeue.start_queue()

    assert calls == [("POST", "/lol-lobby/v2/lobby", {"queueId": 420})]


def test_start_queue_applies_configured_positions_when_client_has_none(capsys):
    ragequeue = RageQueue(
        {
            "ragequeue": {
                "enabled": True,
                "queue_id": 420,
                "first_position": "TOP",
                "second_position": "JUNGLE",
            }
        }
    )
    calls = []

    def fake_lcu_request(method, endpoint, body):
        calls.append((method, endpoint, body))
        if method == "GET" and endpoint == "/lol-lobby/v2/lobby":
            return FakeResponse(
                data={
                    "localMember": {
                        "firstPositionPreference": "UNSELECTED",
                        "secondPositionPreference": "UNSELECTED",
                    }
                }
            )
        return FakeResponse(status_code=200)

    ragequeue.rengar.lcu_request = fake_lcu_request
    ragequeue.start_queue()

    assert calls == [
        ("POST", "/lol-lobby/v2/lobby", {"queueId": 420}),
        ("GET", "/lol-lobby/v2/lobby", ""),
        (
            "PUT",
            "/lol-lobby/v2/lobby/members/localMember/position-preferences",
            {"firstPreference": "TOP", "secondPreference": "JUNGLE"},
        ),
        ("POST", "/lol-lobby/v2/lobby/matchmaking/search", ""),
    ]
    assert capsys.readouterr().out == ""


def test_start_queue_preserves_positions_selected_in_client():
    ragequeue = RageQueue(
        {
            "ragequeue": {
                "enabled": True,
                "queue_id": 400,
                "first_position": "TOP",
                "second_position": "JUNGLE",
            }
        }
    )
    calls = []

    def fake_lcu_request(method, endpoint, body):
        calls.append((method, endpoint, body))
        if method == "GET" and endpoint == "/lol-lobby/v2/lobby":
            return FakeResponse(
                data={
                    "localMember": {
                        "firstPositionPreference": "MIDDLE",
                        "secondPositionPreference": "BOTTOM",
                    }
                }
            )
        return FakeResponse(status_code=200)

    ragequeue.rengar.lcu_request = fake_lcu_request
    ragequeue.start_queue()

    assert not any(method == "PUT" for method, _endpoint, _body in calls)
    assert calls[-1] == (
        "POST",
        "/lol-lobby/v2/lobby/matchmaking/search",
        "",
    )


def test_configure_rejects_duplicate_positions():
    ragequeue = RageQueue(
        {"ragequeue": {"enabled": False, "queue_id": 420}}
    )

    with pytest.raises(ValueError, match="must be different"):
        ragequeue.configure(420, "TOP", "TOP")


def test_deleted_lobby_is_recreated_and_queue_is_restarted():
    ragequeue = RageQueue(
        {"ragequeue": {"enabled": True, "queue_id": 450}}
    )
    phases = iter(["Matchmaking", "Lobby", "None", "Matchmaking"])
    calls = []

    def fake_lcu_request(method, endpoint, body):
        calls.append((method, endpoint, body))
        if endpoint == "/lol-gameflow/v1/gameflow-phase":
            return FakeResponse(data=next(phases))
        return FakeResponse(status_code=200)

    ragequeue.rengar.lcu_request = fake_lcu_request

    ragequeue.check_gameflow()
    ragequeue.check_gameflow()
    ragequeue.check_gameflow()
    ragequeue.check_gameflow()

    assert calls == [
        ("GET", "/lol-gameflow/v1/gameflow-phase", ""),
        ("GET", "/lol-gameflow/v1/gameflow-phase", ""),
        ("GET", "/lol-gameflow/v1/gameflow-phase", ""),
        ("POST", "/lol-lobby/v2/lobby", {"queueId": 450}),
        ("POST", "/lol-lobby/v2/lobby/matchmaking/search", ""),
        ("GET", "/lol-gameflow/v1/gameflow-phase", ""),
    ]


def test_stopping_queue_without_deleting_lobby_does_not_restart():
    ragequeue = RageQueue(
        {"ragequeue": {"enabled": True, "queue_id": 450}}
    )
    phases = iter(["Matchmaking", "Lobby", "Lobby"])
    calls = []

    def fake_lcu_request(method, endpoint, body):
        calls.append((method, endpoint, body))
        return FakeResponse(data=next(phases))

    ragequeue.rengar.lcu_request = fake_lcu_request

    ragequeue.check_gameflow()
    ragequeue.check_gameflow()
    ragequeue.check_gameflow()

    assert all(method == "GET" for method, _endpoint, _body in calls)


@pytest.mark.parametrize("phase", ["None", "Lobby"])
def test_enabled_ragequeue_starts_on_initial_eligible_phase(phase):
    ragequeue = RageQueue(
        {"ragequeue": {"enabled": True, "queue_id": 450}}
    )
    calls = []

    def fake_lcu_request(method, endpoint, body):
        calls.append((method, endpoint, body))
        if endpoint == "/lol-gameflow/v1/gameflow-phase":
            return FakeResponse(data=phase)
        return FakeResponse(status_code=200)

    ragequeue.rengar.lcu_request = fake_lcu_request

    ragequeue.check_gameflow()
    ragequeue.check_gameflow()

    assert calls == [
        ("GET", "/lol-gameflow/v1/gameflow-phase", ""),
        ("POST", "/lol-lobby/v2/lobby", {"queueId": 450}),
        ("POST", "/lol-lobby/v2/lobby/matchmaking/search", ""),
        ("GET", "/lol-gameflow/v1/gameflow-phase", ""),
    ]
