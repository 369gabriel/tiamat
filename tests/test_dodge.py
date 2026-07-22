import pytest

from Dodge import dodge


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


class FakeRengar:
    def __init__(self, statuses):
        self.statuses = iter(statuses)
        self.calls = 0

    def lcu_request(self, _method, _endpoint, _body):
        self.calls += 1
        return FakeResponse(next(self.statuses))


def test_dodge_stops_after_first_success():
    api = FakeRengar([200])

    dodge(api)

    assert api.calls == 1


def test_dodge_retries_non_success_responses():
    api = FakeRengar([500, 500, 204])

    dodge(api)

    assert api.calls == 3


def test_dodge_raises_after_bounded_attempts():
    api = FakeRengar([500] * 6)

    with pytest.raises(RuntimeError, match="HTTP 500"):
        dodge(api)

    assert api.calls == 6
