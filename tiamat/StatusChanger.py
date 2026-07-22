from Rengar import Rengar


def change_status(status, rengar=None):
    api = rengar or Rengar()
    response = api.lcu_request("PUT", "/lol-chat/v1/me", {"statusMessage": status})
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f"Could not change status message (HTTP {response.status_code})")
    return status
