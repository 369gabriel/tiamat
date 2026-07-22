from Rengar import Rengar


def change_profile_icon(icon_id, rengar=None):
    icon_id = int(icon_id)
    if icon_id < 1:
        raise ValueError("Icon ID must be a positive number")

    api = rengar or Rengar()
    response = api.lcu_request(
        "PUT", "/lol-summoner/v1/current-summoner/icon", {"profileIconId": icon_id}
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(f"Could not change profile icon (HTTP {response.status_code})")
    return icon_id
