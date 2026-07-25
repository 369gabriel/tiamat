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
        "https://u.gg/lol/multisearch?"
        "summoners=Player%20One-EUW,Player%20Two-1234&region=euw1"
    )


def test_ugg_reveal_url_matches_provider_format():
    players = [
        "Example One#TAG1",
        "Example Two#TAG2",
        "Jogador Três#BR1",
        "Nome Com Espaço#TEST",
        "Final Player#END",
    ]

    assert build_reveal_url("ugg", "br", players) == (
        "https://u.gg/lol/multisearch?"
        "summoners=Example%20One-TAG1,Example%20Two-TAG2,"
        "Jogador%20Tr%C3%AAs-BR1,Nome%20Com%20Espa%C3%A7o-TEST,"
        "Final%20Player-END&region=br1"
    )


def test_unknown_reveal_provider_is_rejected():
    with pytest.raises(ValueError, match="Unsupported"):
        build_reveal_url("unknown", "euw", PLAYERS)
