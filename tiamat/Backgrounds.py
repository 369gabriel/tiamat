import requests

from Rengar import Rengar


SKINS_URL = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/skins.json"


def fetch_all_champion_skins():
    response = requests.get(SKINS_URL, timeout=10)
    if response.status_code != 200:
        raise RuntimeError(f"Could not fetch skins (HTTP {response.status_code})")

    skins = []
    for skin_id, skin_data in response.json().items():
        load_screen_path = skin_data.get("loadScreenPath", "")
        marker = "ASSETS/Characters/"
        marker_start = load_screen_path.find(marker)
        if marker_start == -1:
            champion_name = "Unknown"
        else:
            name_start = marker_start + len(marker)
            name_end = load_screen_path.find("/", name_start)
            champion_name = load_screen_path[name_start:name_end]

        if skin_data.get("questSkinInfo"):
            for tier in skin_data["questSkinInfo"].get("tiers", []):
                skins.append(
                    {
                        "id": str(tier.get("id", "")),
                        "name": tier.get("name", ""),
                        "champion": champion_name,
                    }
                )
        else:
            skins.append(
                {
                    "id": str(skin_id),
                    "name": "Default" if skin_data.get("isBase") else skin_data.get("name", ""),
                    "champion": champion_name,
                }
            )
    return skins


def search_skins_by_name(skins, search_query):
    query = search_query.strip().lower()
    if not query:
        return []
    return [
        skin
        for skin in skins
        if query in skin["champion"].lower() or query in skin["name"].lower()
    ]


def change_profile_background(skin_id, rengar=None):
    skin_id = int(skin_id)
    api = rengar or Rengar()
    response = api.lcu_request(
        "POST",
        "/lol-summoner/v1/current-summoner/summoner-profile",
        {"key": "backgroundSkinId", "value": skin_id},
    )
    if response.status_code != 200:
        raise RuntimeError(f"Could not change profile background (HTTP {response.status_code})")
    return skin_id
