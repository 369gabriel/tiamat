from Rengar import Rengar


def change_riotid(name, tag, rengar=None):
    name = name.strip()
    tag = tag.strip().lstrip("#")
    if not name or not tag:
        raise ValueError("Name and tag are required")
    if len(name) > 16:
        raise ValueError("Name must be 16 characters or fewer")
    if len(tag) > 5:
        raise ValueError("Tag must be 5 characters or fewer")

    api = rengar or Rengar()
    response = api.lcu_request(
        "POST", "/lol-summoner/v1/save-alias", {"gameName": name, "tagLine": tag}
    )
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f"Could not change Riot ID (HTTP {response.status_code})")
    return f"{name}#{tag}"
