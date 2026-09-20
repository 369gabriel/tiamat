from time import sleep

from Rengar import Rengar


_RENAME_ERRORS = {
    "name_change_forbidden": "Riot is not allowing this account to change its Riot ID right now",
    "name_not_available": "That Riot ID is unavailable or invalid",
    "rate_limited": "Too many rename attempts; try again later",
    "server_error": "Riot could not process the rename; try again later",
}


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

    # The endpoint returns HTTP 200 even when Riot rejects the rename.
    try:
        result = response.json()
    except ValueError as error:
        raise RuntimeError("Riot returned an invalid rename response; the change is unconfirmed") from error
    if not isinstance(result, dict) or not isinstance(result.get("isSuccess"), bool):
        raise RuntimeError("Riot returned an invalid rename response; the change is unconfirmed")
    if not result["isSuccess"]:
        code = result.get("errorCode")
        reason = _RENAME_ERRORS.get(str(code), "Riot rejected the Riot ID change")
        details = ": ".join(str(value) for value in (code, result.get("errorMessage")) if value)
        raise RuntimeError(f"{reason} ({details})" if details else reason)

    # Allow the client to refresh, without resubmitting the rename.
    unconfirmed = (
        "Riot accepted the request, but the client has not confirmed the requested Riot ID. "
        "Check your account before trying again."
    )
    for attempt in range(3):
        if attempt:
            sleep(0.5)
        try:
            current = api.lcu_request("GET", "/lol-summoner/v1/current-summoner", "")
            summoner = current.json() if 200 <= current.status_code < 300 else None
        except Exception as error:
            raise RuntimeError(unconfirmed) from error
        if isinstance(summoner, dict) and (
            summoner.get("gameName") == name and summoner.get("tagLine") == tag
        ):
            return f"{name}#{tag}"
    raise RuntimeError(unconfirmed)
