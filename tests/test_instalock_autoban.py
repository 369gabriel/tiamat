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
                "actions": [
                    [
                        {
                            "id": 9,
                            "actorCellId": 1,
                            "type": action_type,
                            "completed": False,
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
