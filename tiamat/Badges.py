from Rengar import Rengar


BADGE_MODES = {"empty", "copy", "glitched"}


def _get_player_data(rengar):
    response = rengar.lcu_request(
        "GET", "/lol-challenges/v1/summary-player-data/local-player", ""
    )
    if response.status_code != 200:
        raise RuntimeError(f"Could not read profile badges (HTTP {response.status_code})")
    return response.json()


def change_profile_badges(mode, glitched_id=None, rengar=None):
    if mode not in BADGE_MODES:
        raise ValueError("Unknown badge mode")

    api = rengar or Rengar()
    data = _get_player_data(api)
    top_challenges = data.get("topChallenges", [])

    if mode == "empty":
        challenge_ids = []
    elif mode == "copy":
        if not top_challenges:
            raise ValueError("There are no badges to copy")
        challenge_ids = [int(top_challenges[0]["id"])] * 3
    else:
        glitched_id = int(glitched_id)
        if not 0 <= glitched_id <= 5:
            raise ValueError("Glitched badge ID must be between 0 and 5")
        challenge_ids = [glitched_id] * 3

    payload = {"challengeIds": challenge_ids}
    title_id = data.get("title", {}).get("itemId", -1)
    banner_id = data.get("bannerId", "")
    if title_id != -1:
        payload["title"] = str(title_id)
    if banner_id:
        payload["bannerAccent"] = banner_id

    response = api.lcu_request(
        "POST", "/lol-challenges/v1/update-player-preferences/", payload
    )
    if response.status_code not in (200, 201, 204):
        raise RuntimeError(f"Could not update profile badges (HTTP {response.status_code})")
    return challenge_ids
