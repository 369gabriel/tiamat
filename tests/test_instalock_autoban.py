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
        if endpoint == "/lol-champ-select/v1/pickable-champion-ids":
            return FakeResponse([103])
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


@pytest.mark.parametrize(("available", "fallback", "expected"), [
    ([103, 99], "Lux", (103, "Ahri")),
    ([99], "Lux", (99, "Lux")),
    ([99], None, None),
    ([], "Lux", None),
])
def test_optional_fallback_respects_champion_availability(available, fallback, expected):
    automation = InstalockAutoban({
        "instalock": {"champion": "Ahri", "fallback_champion": fallback}, "autoban": {},
    })
    automation.champ_dict = {"ahri": 103, "lux": 99}
    automation.rengar.lcu_request = lambda *_: FakeResponse(available)
    assert automation.choose_pick({}) == expected


@pytest.mark.parametrize("session", [
    {"bans": {"myTeamBans": [103], "theirTeamBans": []}},
    {"actions": [[{"type": "ban", "completed": True, "championId": 103}]]},
    {"theirTeam": [{"cellId": 7, "championId": 103}],
     "actions": [[{"type": "pick", "completed": True, "actorCellId": 7}]]},
])
def test_fallback_skips_banned_or_taken_main(session):
    automation = InstalockAutoban({
        "instalock": {"champion": "Ahri", "fallback_champion": "Lux"}, "autoban": {},
    })
    automation.champ_dict = {"ahri": 103, "lux": 99}
    automation.rengar.lcu_request = lambda *_: FakeResponse([103, 99])
    assert automation.choose_pick(session) == (99, "Lux")


def test_hover_does_not_trigger_fallback():
    automation = InstalockAutoban({
        "instalock": {"champion": "Ahri", "fallback_champion": "Lux"}, "autoban": {},
    })
    automation.champ_dict = {"ahri": 103, "lux": 99}
    automation.rengar.lcu_request = lambda *_: FakeResponse([103, 99])
    assert automation.choose_pick({
        "myTeam": [{"cellId": 1, "championId": 103}],
        "actions": [[{"type": "pick", "completed": False, "actorCellId": 1}]],
    }) == (103, "Ahri")


def test_fallback_is_saved_cleared_and_optional_for_old_configs(monkeypatch):
    saved = []
    monkeypatch.setattr(automation_module, "save_config", lambda config: saved.append(config))
    automation = InstalockAutoban({"instalock": {}, "autoban": {}})
    automation.champ_dict = {"ahri": 103, "lux": 99}
    assert automation.fallback_champion is None
    automation.configure_instalock("Ahri", "Lux")
    assert saved[-1]["instalock"]["fallback_champion"] == "Lux"
    assert InstalockAutoban(saved[-1]).fallback_champion == "Lux"
    automation.configure_instalock("Ahri", None)
    assert saved[-1]["instalock"]["fallback_champion"] is None
    with pytest.raises(ValueError, match="different"):
        automation.configure_instalock("Ahri", "Ahri")


def test_availability_failure_does_not_choose_fallback():
    automation = InstalockAutoban({
        "instalock": {"champion": "Ahri", "fallback_champion": "Lux"}, "autoban": {},
    })
    response = FakeResponse([])
    response.status_code = 503
    automation.rengar.lcu_request = lambda *_: response
    with pytest.raises(RuntimeError, match="available champions"):
        automation.choose_pick({})


@pytest.mark.parametrize(("available", "fallback", "expected"), [
    ([103, 99], "Lux", 103),
    ([99], "Lux", 99),
    ([99], None, None),
    ([], "Lux", None),
])
def test_monitor_locks_only_an_available_configured_pick(available, fallback, expected, monkeypatch):
    events = []
    automation = InstalockAutoban({
        "instalock": {"enabled": True, "champion": "Ahri", "fallback_champion": fallback,
                      "delay_seconds": 0},
        "autoban": {},
    }, lambda level, message: events.append((level, message)))
    automation.champ_dict = {"ahri": 103, "lux": 99}
    picks = []

    def request(method, endpoint, body):
        if endpoint.endswith("pickable-champion-ids"):
            return FakeResponse(available)
        if method == "PATCH":
            picks.append(body["championId"])
            return FakeResponse()
        return FakeResponse({
            "localPlayerCellId": 1,
            "actions": [[{"id": 9, "actorCellId": 1, "type": "pick",
                          "completed": False, "isInProgress": True}]],
        })

    def stop(_seconds):
        raise StopMonitor

    automation.rengar.lcu_request = request
    monkeypatch.setattr(automation_module.time, "sleep", stop)
    with pytest.raises(StopMonitor):
        automation.monitor_champ_select()
    assert picks == ([] if expected is None else [expected])
    if expected == 99:
        assert events == [("success", "Locked Lux")]
    elif expected is None:
        assert events == [("warning", "No configured champion is available; choose a champion manually")]
