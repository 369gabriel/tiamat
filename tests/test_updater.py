from unittest.mock import Mock

import requests

from Updater import check_for_update, is_newer, parse_version


def release_session(status=200, payload=None, error=None):
    session = Mock()
    if error:
        session.get.side_effect = error
    else:
        session.get.return_value = Mock(
            status_code=status, json=Mock(return_value=payload or {})
        )
    return session


def test_parse_version_handles_tags():
    assert parse_version("v2.1.1") == (2, 1, 1)
    assert parse_version("2.0") == (2, 0)
    assert parse_version("v3.0.0-beta") == (3, 0, 0)
    assert parse_version("latest") is None


def test_is_newer_compares_numerically():
    assert is_newer("v2.10", "2.9")
    assert is_newer("v2.1.2", "2.1.1")
    assert is_newer("v3", "2.9.9")
    assert not is_newer("v2.1", "2.1.0")
    assert not is_newer("v2.0", "2.1.1")
    assert not is_newer("garbage", "2.1.1")


def test_check_for_update_returns_newer_release():
    session = release_session(
        payload={"tag_name": "v2.2.0", "html_url": "https://example.test/r"}
    )
    assert check_for_update("2.1.1", session) == ("2.2.0", "https://example.test/r")


def test_check_for_update_ignores_same_or_older_release():
    session = release_session(payload={"tag_name": "v2.1.1"})
    assert check_for_update("2.1.1", session) is None


def test_check_for_update_ignores_prereleases():
    session = release_session(payload={"tag_name": "v9.0", "prerelease": True})
    assert check_for_update("2.1.1", session) is None


def test_check_for_update_is_silent_on_failures():
    assert check_for_update("2.1.1", release_session(status=403)) is None
    assert (
        check_for_update(
            "2.1.1", release_session(error=requests.exceptions.ConnectionError())
        )
        is None
    )
