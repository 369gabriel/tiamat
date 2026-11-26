import webbrowser
from urllib.parse import quote

from ClientState import resolve_team_riot_ids
from Rengar import Rengar


REVEAL_PROVIDERS = {
    "porofessor": "Porofessor",
    "opgg": "OP.GG",
    "ugg": "U.GG",
}

UGG_REGIONS = {
    "br": "br1",
    "eune": "eun1",
    "euw": "euw1",
    "jp": "jp1",
    "kr": "kr",
    "lan": "la1",
    "las": "la2",
    "na": "na1",
    "oce": "oc1",
    "ru": "ru",
    "tr": "tr1",
    "ph": "ph2",
    "sg": "sg2",
    "th": "th2",
    "tw": "tw2",
    "vn": "vn2",
}


def build_reveal_url(provider, region, summoner_names):
    if provider not in REVEAL_PROVIDERS:
        raise ValueError("Unsupported Multi-Search provider")

    region = region.lower()
    if provider == "porofessor":
        players = quote(",".join(summoner_names), safe=",")
        return (
            f"https://porofessor.gg/pregame/{region}/{players}/soloqueue/season"
        )
    if provider == "opgg":
        players = quote(",".join(summoner_names), safe=",")
        return f"https://www.op.gg/multisearch/{region}?summoners={players}"

    ugg_names = []
    for riot_id in summoner_names:
        game_name, separator, tag_line = riot_id.rpartition("#")
        ugg_names.append(
            f"{game_name}-{tag_line}" if separator else riot_id
        )
    players = quote(",".join(ugg_names), safe=",")
    ugg_region = UGG_REGIONS.get(region, region)
    return f"https://u.gg/lol/multisearch?summoners={players}&region={ugg_region}"


def reveal(provider="porofessor", rengar=None, open_browser=True):
    api = rengar or Rengar()
    champ_select = api.lcu_request("GET", "/lol-champ-select/v1/session", "")
    if champ_select.status_code != 200 or "RPC_ERROR" in champ_select.text:
        raise RuntimeError("Lobby reveal is only available during champion select")

    session = champ_select.json()
    names_by_cell, unmatched = resolve_team_riot_ids(api, session)
    summoner_names = list(names_by_cell.values()) + list(unmatched)

    region_response = api.lcu_request("GET", "/riotclient/region-locale", "")
    region = (
        region_response.json().get("webRegion", "")
        if region_response.status_code == 200
        else ""
    )
    if not region or not summoner_names:
        raise RuntimeError("Could not read the lobby region or summoner names")

    url = build_reveal_url(provider, region, summoner_names)
    if open_browser:
        webbrowser.open(url)
    return url
