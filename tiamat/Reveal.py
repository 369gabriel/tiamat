import webbrowser
from urllib.parse import quote

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
        raise ValueError("Unsupported Lobby Reveal provider")

    region = region.lower()
    players = quote(",".join(summoner_names), safe=",")
    if provider == "porofessor":
        return (
            f"https://porofessor.gg/pregame/{region}/{players}/soloqueue/season"
        )
    if provider == "opgg":
        return f"https://www.op.gg/multisearch/{region}?summoners={players}"

    ugg_region = UGG_REGIONS.get(region, region)
    return f"https://u.gg/multisearch?summoners={players}&region={ugg_region}"


def reveal(provider="porofessor", rengar=None, open_browser=True):
    api = rengar or Rengar()
    champ_select = api.lcu_request("GET", "/lol-champ-select/v1/session", "")
    if champ_select.status_code != 200 or "RPC_ERROR" in champ_select.text:
        raise RuntimeError("Lobby reveal is only available during champion select")

    session = champ_select.json()
    summoner_names = []
    hidden_names = any(
        player.get("nameVisibilityType") == "HIDDEN"
        for player in session.get("myTeam", [])
    )

    if hidden_names:
        participants = api.riot_request("GET", "/chat/v5/participants", "")
        for participant in participants.json().get("participants", []):
            if "champ-select" in participant.get("cid", ""):
                summoner_names.append(
                    f"{participant['game_name']}#{participant['game_tag']}"
                )
    else:
        for player in session.get("myTeam", []):
            summoner_id = player.get("summonerId")
            if not summoner_id or summoner_id == "0":
                continue
            response = api.lcu_request(
                "GET", f"/lol-summoner/v1/summoners/{summoner_id}", ""
            )
            if response.status_code == 200:
                summoner = response.json()
                summoner_names.append(
                    f"{summoner['gameName']}#{summoner['tagLine']}"
                )

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
