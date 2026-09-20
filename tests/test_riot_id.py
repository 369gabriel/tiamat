from unittest.mock import Mock

import pytest

from Riotidchanger import change_riotid


def response(payload=None, status=200):
    result = Mock(status_code=status)
    result.json.return_value = payload
    return result


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr("Riotidchanger.sleep", lambda _: None)
    return Mock()


@pytest.mark.parametrize("code", [
    "name_change_forbidden", "name_not_available", "rate_limited", "server_error", "unknown",
])
def test_http_success_with_riot_rejection_is_not_success(api, code):
    api.lcu_request.return_value = response({
        "isSuccess": False, "errorCode": code, "errorMessage": "rename rejected",
    })
    with pytest.raises(RuntimeError, match=code):
        change_riotid("Player", "TAG", api)
    assert api.lcu_request.call_count == 1


@pytest.mark.parametrize("payload", [None, False, [], {}, {"isSuccess": "false"}])
def test_invalid_result_cannot_report_success(api, payload):
    api.lcu_request.return_value = response(payload)
    with pytest.raises(RuntimeError, match="unconfirmed"):
        change_riotid("Player", "TAG", api)


def test_non_json_result_cannot_report_success(api):
    api.lcu_request.return_value = response()
    api.lcu_request.return_value.json.side_effect = ValueError("invalid JSON")
    with pytest.raises(RuntimeError, match="unconfirmed"):
        change_riotid("Player", "TAG", api)


def test_http_error(api):
    api.lcu_request.return_value = response(status=403)
    with pytest.raises(RuntimeError, match="HTTP 403"):
        change_riotid("Player", "TAG", api)


def test_confirmed_rename_normalizes_input_and_waits_for_refresh(api):
    api.lcu_request.side_effect = [
        response({"isSuccess": True}),
        response({"gameName": "Old", "tagLine": "TAG"}),
        response({"gameName": "Player", "tagLine": "TAG"}),
    ]
    assert change_riotid(" Player ", " #TAG ", api) == "Player#TAG"
    assert api.lcu_request.call_args_list[0].args == (
        "POST", "/lol-summoner/v1/save-alias", {"gameName": "Player", "tagLine": "TAG"},
    )
    assert [call.args[0] for call in api.lcu_request.call_args_list] == ["POST", "GET", "GET"]


@pytest.mark.parametrize("current", [
    {"gameName": "Old", "tagLine": "TAG"},
    {"gameName": "Player", "tagLine": "OLD"},
    {}, None,
])
def test_unchanged_or_missing_account_never_reports_success(api, current):
    api.lcu_request.side_effect = [response({"isSuccess": True})] + [response(current)] * 3
    with pytest.raises(RuntimeError, match="has not confirmed"):
        change_riotid("Player", "TAG", api)
    assert [call.args[0] for call in api.lcu_request.call_args_list] == ["POST", "GET", "GET", "GET"]


def test_verification_connection_failure_is_unconfirmed(api):
    api.lcu_request.side_effect = [response({"isSuccess": True}), ConnectionError("disconnected")]
    with pytest.raises(RuntimeError, match="Check your account before trying again"):
        change_riotid("Player", "TAG", api)


def test_verification_http_failure_is_unconfirmed(api):
    api.lcu_request.side_effect = [response({"isSuccess": True})] + [response(status=503)] * 3
    with pytest.raises(RuntimeError, match="has not confirmed"):
        change_riotid("Player", "TAG", api)
