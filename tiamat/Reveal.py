import webbrowser

from Rengar import Rengar
from termcolor import colored


def reveal():
    rengar = Rengar()
    champ_select = rengar.lcu_request("GET", "/lol-champ-select/v1/session", "")

    if champ_select.status_code == 200 and "RPC_ERROR" not in champ_select.text:
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
                        summ_name = (
                            f"{participant['game_name']}%23{participant['game_tag']}"
                        )
                        summ_names.append(summ_name)

            region = ""
            get_region = rengar.lcu_request("GET", "/riotclient/region-locale", "")
            if get_region.status_code == 200:
                region_data = get_region.json()
                region = region_data.get("webRegion", "")

            if region and summ_names:
                summ_names_str = ",".join(summ_names)

                url = f"https://porofessor.gg/pregame/{region}/{summ_names_str}/soloqueue/season"
                webbrowser.open(url)

                return url
            else:
                return "Failed to get region or summoner names"
    else:
        print(colored("\nNot in champion select.\n", "red"))
