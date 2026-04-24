import webbrowser

from Rengar import get_shared_rengar
from termcolor import colored

_REGION_CACHE = None


class ChampionSelectNotFoundError(Exception):
    pass


def _get_region(rengar):
    global _REGION_CACHE

    if _REGION_CACHE:
        return _REGION_CACHE

    get_region = rengar.lcu_request("GET", "/riotclient/region-locale", "")
    if get_region.status_code != 200:
        return ""

    region_data = get_region.json()
    _REGION_CACHE = region_data.get("webRegion", "")
    return _REGION_CACHE


def reveal():
    rengar = get_shared_rengar()
    champ_select = rengar.lcu_request("GET", "/lol-champ-select/v1/session", "")

    if champ_select.status_code != 200 or "RPC_ERROR" in champ_select.text:
        print(colored("\nNot in champion select.\n", "red"))
        return None

    champ_select_data = champ_select.json()
    summ_names = []
    is_ranked = False

    if "myTeam" in champ_select_data:
        for player in champ_select_data["myTeam"]:
            if player["nameVisibilityType"] == "HIDDEN":
                is_ranked = True
                break

            summoner_id = player["summonerId"]
            if summoner_id != "0":
                summoner = rengar.lcu_request(
                    "GET", f"/lol-summoner/v1/summoners/{summoner_id}", ""
                )
                if summoner.status_code == 200:
                    summoner_data = summoner.json()
                    summ_name = (
                        f"{summoner_data['gameName']}%23{summoner_data['tagLine']}"
                    )
                    summ_names.append(summ_name)

    if is_ranked:
        summ_names = []
        participants = rengar.riot_request("GET", "/chat/v5/participants", "")
        participants_data = participants.json()

        if "participants" in participants_data:
            for participant in participants_data["participants"]:
                if "champ-select" not in participant["cid"]:
                    continue
                summ_name = f"{participant['game_name']}%23{participant['game_tag']}"
                summ_names.append(summ_name)

    region = _get_region(rengar)
    if not region or not summ_names:
        return "Failed to get region or summoner names"

    summ_names_str = ",".join(summ_names)
    url = f"https://porofessor.gg/pregame/{region}/{summ_names_str}/soloqueue/season"
    webbrowser.open(url)
    return url
