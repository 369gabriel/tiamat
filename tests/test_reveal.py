import pytest

from Reveal import build_reveal_url


PLAYERS = ["Player One#EUW", "Player Two#1234"]


def test_porofessor_reveal_url():
    assert build_reveal_url("porofessor", "euw", PLAYERS) == (
        "https://porofessor.gg/pregame/euw/"
        "Player%20One%23EUW,Player%20Two%231234/soloqueue/season"
    )


def test_opgg_reveal_url():
    assert build_reveal_url("opgg", "euw", PLAYERS) == (
        "https://www.op.gg/multisearch/euw?"
        "summoners=Player%20One%23EUW,Player%20Two%231234"
    )


def test_ugg_reveal_url_maps_platform_region():
    assert build_reveal_url("ugg", "euw", PLAYERS) == (
        "https://u.gg/multisearch?"
        "summoners=Player%20One%23EUW,Player%20Two%231234&region=euw1"
    )


def test_unknown_reveal_provider_is_rejected():
    with pytest.raises(ValueError, match="Unsupported"):
        build_reveal_url("unknown", "euw", PLAYERS)
