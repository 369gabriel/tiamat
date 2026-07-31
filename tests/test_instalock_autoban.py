import pytest

import InstalockAutoban as automation_module
from InstalockAutoban import InstalockAutoban


class StopMonitor(BaseException):
    pass


class FakeResponse:
    status_code = 200
    text = "{}"

    def __init__(self, data=None):
        self.data = data

    def json(self):
        return self.data


def test_champion_list_keeps_canonical_id_for_duplicate_names():
    config = {
        "instalock": {"enabled": False, "champion": "Random"},
        "autoban": {"enabled": True, "champion": "Ahri"},
    }
    automation = InstalockAutoban(config)
    automation.rengar.lcu_request = lambda _method, _endpoint, _body: FakeResponse(
        [
            {"id": 103, "name": "Ahri", "alias": "Ahri"},
            {"id": 60103, "name": "Ahri", "alias": "Jade_Ahri"},
        ]
    )

    automation.update_champion_list()

    assert automation.champ_name_to_id("Ahri") == 103


@pytest.mark.parametrize(
    ("action_type", "config", "expected_delay"),
    [
        (
            "pick",
            {
                "instalock": {
                    "enabled": True,
                    "champion": "Ahri",
                    "delay_seconds": 0.7,
                },
                "autoban": {
                    "enabled": False,
                    "champion": "None",
                    "delay_seconds": 0.3,
                },
            },
            0.7,
        ),
        (
            "ban",
            {
                "instalock": {
                    "enabled": False,
                    "champion": "Ahri",
                    "delay_seconds": 0.3,
                },
                "autoban": {
                    "enabled": True,
                    "champion": "Ahri",
                    "delay_seconds": 1.2,
                },
            },
            1.2,
        ),
    ],
)
def test_champion_automation_uses_configured_delay(
    action_type, config, expected_delay, monkeypatch
):
    automation = InstalockAutoban(config)
    automation.champ_dict = {"ahri": 103}
    patched = False
    sleeps = []

    def fake_request(method, endpoint, _body):
        nonlocal patched
        if method == "PATCH":
            patched = True
            return FakeResponse()
        return FakeResponse(
            {
                "localPlayerCellId": 1,
                "timer": {"phase": "BAN_PICK"},
                "actions": [
                    [
                        {
                            "id": 9,
                            "actorCellId": 1,
                            "type": action_type,
                            "completed": False,
                            "isInProgress": True,
                        }
                    ]
                ],
            }
        )

    def fake_sleep(seconds):
        sleeps.append(seconds)
        if patched:
            raise StopMonitor

    automation.rengar.lcu_request = fake_request
    monkeypatch.setattr(automation_module.time, "sleep", fake_sleep)

    with pytest.raises(StopMonitor):
        automation.monitor_champ_select()

    assert sleeps[0] == expected_delay


@pytest.mark.parametrize(
    ("initial_phase", "initially_in_progress"),
    [("PLANNING", True), ("BAN_PICK", False)],
)
def test_autoban_attempts_regardless_of_client_readiness(
    initial_phase, initially_in_progress, monkeypatch
):
    config = {
        "instalock": {
            "enabled": False,
            "champion": "Random",
            "delay_seconds": 0.3,
        },
        "autoban": {
            "enabled": True,
            "champion": "Ahri",
            "delay_seconds": 0.3,
        },
    }
    events = []
    automation = InstalockAutoban(
        config, lambda level, message: events.append((level, message))
    )
    automation.champ_dict = {"ahri": 103}
    calls = []

    def fake_request(method, endpoint, body):
        calls.append((method, endpoint, body))
        if method != "GET":
            return FakeResponse()

        return FakeResponse(
            {
                "localPlayerCellId": 1,
                "timer": {"phase": initial_phase},
                "actions": [
                    [
                        {
                            "id": 9,
                            "actorCellId": 1,
                            "type": "ban",
                            "completed": False,
                            "isInProgress": initially_in_progress,
                        }
                    ]
                ],
            }
        )

    def fake_sleep(_seconds):
        if any(method == "PATCH" for method, _endpoint, _body in calls):
            raise StopMonitor

    automation.rengar.lcu_request = fake_request
    monkeypatch.setattr(automation_module.time, "sleep", fake_sleep)

    with pytest.raises(StopMonitor):
        automation.monitor_champ_select()

    assert (
        "PATCH",
        "/lol-champ-select/v1/session/actions/9",
        {"completed": True, "championId": 103},
    ) in calls
    assert events == []


def test_autoban_reports_success_only_after_confirmation(monkeypatch):
    config = {
        "instalock": {
            "enabled": False,
            "champion": "Random",
            "delay_seconds": 0.3,
        },
        "autoban": {
            "enabled": True,
            "champion": "Ahri",
            "delay_seconds": 0.3,
        },
    }
    events = []
    automation = InstalockAutoban(
        config, lambda level, message: events.append((level, message))
    )
    automation.champ_dict = {"ahri": 103}
    completed = False

    def fake_request(method, _endpoint, _body):
        nonlocal completed
        if method == "PATCH":
            completed = True
            return FakeResponse()
        return FakeResponse(
            {
                "localPlayerCellId": 1,
                "actions": [
                    [
                        {
                            "id": 9,
                            "actorCellId": 1,
                            "type": "ban",
                            "completed": completed,
                            "isInProgress": not completed,
                            "championId": 103 if completed else 0,
                        }
                    ]
                ],
            }
        )

    def fake_sleep(_seconds):
        if completed:
            raise StopMonitor

    automation.rengar.lcu_request = fake_request
    monkeypatch.setattr(automation_module.time, "sleep", fake_sleep)

    with pytest.raises(StopMonitor):
        automation.monitor_champ_select()

    assert events == [("success", "Banned Ahri")]
