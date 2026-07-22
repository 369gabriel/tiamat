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


def test_dodge_sends_five_requests_after_success():
    api = FakeRengar([200] * 5)

    dodge(api)

    assert api.calls == 5


def test_dodge_succeeds_if_any_of_the_five_requests_succeeds():
    api = FakeRengar([500, 500, 204, 500, 500])

    dodge(api)

    assert api.calls == 5


def test_dodge_raises_after_bounded_attempts():
    api = FakeRengar([500] * 5)

    with pytest.raises(RuntimeError, match="HTTP 500"):
        dodge(api)

    assert api.calls == 5
