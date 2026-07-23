import requests
from functools import lru_cache

from Rengar import Rengar


SKINS_URL = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/skins.json"
ASSET_BASE_URL = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default"


@lru_cache(maxsize=1)
def fetch_skin_catalog():
    response = requests.get(SKINS_URL, timeout=10)
    if response.status_code != 200:
        raise RuntimeError(f"Could not fetch skins (HTTP {response.status_code})")
    return response.json()


def communitydragon_asset_url(asset_path):
    if not asset_path:
        return ""
    prefix = "/lol-game-data/assets"
    if asset_path.startswith(prefix):
        asset_path = asset_path[len(prefix):]
    return f"{ASSET_BASE_URL}{asset_path}".lower()


def get_skin_assets(skin_id):
    skin = fetch_skin_catalog().get(str(skin_id), {})
    return {
        "backgroundUrl": communitydragon_asset_url(
            skin.get("uncenteredSplashPath") or skin.get("splashPath")
        ),
        "tileUrl": communitydragon_asset_url(skin.get("tilePath")),
    }


@lru_cache(maxsize=12)
def fetch_skin_background(skin_id):
    background_url = get_skin_assets(skin_id)["backgroundUrl"]
    if not background_url:
        raise RuntimeError(f"Could not find background asset for skin {skin_id}")
    response = requests.get(background_url, timeout=15)
    if response.status_code != 200:
        raise RuntimeError(
            f"Could not fetch background asset (HTTP {response.status_code})"
        )
    return response.content, response.headers.get("content-type", "image/jpeg")


def fetch_all_champion_skins():
    skins = []
    for skin_id, skin_data in fetch_skin_catalog().items():
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
                        "tileUrl": communitydragon_asset_url(tier.get("tilePath")),
                        "splashUrl": communitydragon_asset_url(
                            tier.get("splashPath") or tier.get("uncenteredSplashPath")
                        ),
                    }
                )
        else:
            skins.append(
                {
                    "id": str(skin_id),
                    "name": "Default" if skin_data.get("isBase") else skin_data.get("name", ""),
                    "champion": champion_name,
                    "tileUrl": communitydragon_asset_url(skin_data.get("tilePath")),
                    "splashUrl": communitydragon_asset_url(
                        skin_data.get("splashPath")
                        or skin_data.get("uncenteredSplashPath")
                    ),
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
