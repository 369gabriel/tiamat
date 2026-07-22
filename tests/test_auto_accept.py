import pytest

import AutoAccept as auto_accept_module
from AutoAccept import AutoAccept


class FakeResponse:
    status_code = 200

    def json(self):
        return {"searchState": "Found"}


class FailedResponse:
    status_code = 500


class StopMonitor(Exception):
    pass


def test_monitor_queue_continues_after_lcu_error(monkeypatch):
    auto_accept = AutoAccept({"auto_accept": {"enabled": True}})
    calls = []

    def fake_lcu_request(method, endpoint, body):
        calls.append((method, endpoint, body))
        if len(calls) == 1:
            raise RuntimeError("client is still starting")
        return FakeResponse()

    sleep_count = 0

    def fake_sleep(_seconds):
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count == 2:
            raise StopMonitor

    auto_accept.rengar.lcu_request = fake_lcu_request
    monkeypatch.setattr(auto_accept_module.time, "sleep", fake_sleep)

    with pytest.raises(StopMonitor):
        auto_accept.monitor_queue()

    assert calls == [
        ("GET", "/lol-lobby/v2/lobby/matchmaking/search-state", ""),
        ("GET", "/lol-lobby/v2/lobby/matchmaking/search-state", ""),
        ("POST", "/lol-matchmaking/v1/ready-check/accept", ""),
    ]


def test_accept_match_rejects_failed_response():
    auto_accept = AutoAccept({"auto_accept": {"enabled": True}})
    auto_accept.rengar.lcu_request = lambda _method, _endpoint, _body: FailedResponse()

    with pytest.raises(RuntimeError, match="HTTP 500"):
        auto_accept.accept_match()
