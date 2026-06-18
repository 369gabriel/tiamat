import ast
from pathlib import Path

import pytest
import requests

import Rengar as rengar_module
from Rengar import Rengar


class FakeProcess:
    def __init__(self, info):
        self.info = info


class FakeResponse:
    status_code = 200
    text = "{}"

    def json(self):
        return {}


def test_find_league_client_credentials_handles_missing_cmdline(monkeypatch):
    processes = [
        FakeProcess({"name": "LeagueClientUx.exe", "cmdline": None}),
        FakeProcess(
            {
                "name": "LeagueClientUx.exe",
                "cmdline": ["--app-port=1234", "--remoting-auth-token=token"],
            }
        ),
    ]
    monkeypatch.setattr(rengar_module.psutil, "process_iter", lambda *args, **kwargs: processes)

    assert rengar_module.find_league_client_credentials() == ("1234", "token")


def test_find_riot_client_credentials_handles_missing_name_and_cmdline(monkeypatch):
    processes = [
        FakeProcess({"name": None, "cmdline": None}),
        FakeProcess(
            {
                "name": "LeagueClientUx.exe",
                "cmdline": [
                    "--riotclient-app-port=5678",
                    "--riotclient-auth-token=riot-token",
                ],
            }
        ),
    ]
    monkeypatch.setattr(rengar_module.psutil, "process_iter", lambda *args, **kwargs: processes)

    assert rengar_module.find_riot_client_credentials() == ("5678", "riot-token")


def test_lcu_request_retries_without_double_encoding_body(monkeypatch):
    monkeypatch.setattr(
        rengar_module, "find_league_client_credentials", lambda: ("1234", "token")
    )
    monkeypatch.setattr(
        rengar_module, "find_riot_client_credentials", lambda: ("5678", "riot-token")
    )
    monkeypatch.setattr(rengar_module, "check_league_client", lambda: ("1234", "token"))

    calls = []

    def fake_request(method, url, headers, data, verify, timeout):
        calls.append((method, url, headers, data, verify, timeout))
        if len(calls) == 1:
            raise requests.exceptions.ConnectionError("temporary failure")
        return FakeResponse()

    monkeypatch.setattr(rengar_module.requests, "request", fake_request)

    response = Rengar().lcu_request("POST", "/endpoint", {"key": "value"})

    assert response.status_code == 200
    assert len(calls) == 2
    assert calls[0][3] == '{"key": "value"}'
    assert calls[1][3] == '{"key": "value"}'
    assert calls[1][1] == "https://127.0.0.1:1234/endpoint"


def test_lcu_request_raises_after_bounded_retries(monkeypatch):
    monkeypatch.setattr(
        rengar_module, "find_league_client_credentials", lambda: ("1234", "token")
    )
    monkeypatch.setattr(rengar_module, "find_riot_client_credentials", lambda: (None, None))
    monkeypatch.setattr(rengar_module, "check_league_client", lambda: ("1234", "token"))

    calls = []

    def fake_request(*args, **kwargs):
        calls.append((args, kwargs))
        raise requests.exceptions.ConnectionError("still down")

    monkeypatch.setattr(rengar_module.requests, "request", fake_request)

    with pytest.raises(requests.exceptions.ConnectionError):
        Rengar().lcu_request("GET", "/endpoint", "")

    assert len(calls) == rengar_module.REQUEST_RETRIES + 1


def test_invalid_method_raises_value_error(monkeypatch):
    monkeypatch.setattr(
        rengar_module, "find_league_client_credentials", lambda: ("1234", "token")
    )
    monkeypatch.setattr(rengar_module, "find_riot_client_credentials", lambda: (None, None))

    with pytest.raises(ValueError):
        Rengar().lcu_request("TRACE", "/endpoint", "")


def test_missing_credentials_raise_clear_error(monkeypatch):
    monkeypatch.setattr(rengar_module, "find_league_client_credentials", lambda: (None, None))
    monkeypatch.setattr(rengar_module, "find_riot_client_credentials", lambda: (None, None))
    monkeypatch.setattr(rengar_module, "check_league_client", lambda: (None, None))

    with pytest.raises(RuntimeError, match="league client credentials"):
        Rengar().lcu_request("GET", "/endpoint", "")


def test_no_module_level_rengar_instances():
    project_root = Path(__file__).resolve().parents[1]

    offenders = []
    for path in (project_root / "tiamat").glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in tree.body:
            if isinstance(node, ast.Assign):
                if isinstance(node.value, ast.Call) and getattr(node.value.func, "id", None) == "Rengar":
                    offenders.append(f"{path.name}:{node.lineno}")

    assert offenders == []
