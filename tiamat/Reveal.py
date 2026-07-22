import webbrowser

from Rengar import Rengar


def reveal(rengar=None, open_browser=True):
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
                    f"{participant['game_name']}%23{participant['game_tag']}"
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
                    f"{summoner['gameName']}%23{summoner['tagLine']}"
                )

    region_response = api.lcu_request("GET", "/riotclient/region-locale", "")
    region = region_response.json().get("webRegion", "") if region_response.status_code == 200 else ""
    if not region or not summoner_names:
        raise RuntimeError("Could not read the lobby region or summoner names")

    url = (
        f"https://porofessor.gg/pregame/{region}/"
        f"{','.join(summoner_names)}/soloqueue/season"
    )
    if open_browser:
        webbrowser.open(url)
    return url
