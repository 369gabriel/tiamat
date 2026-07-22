from Rengar import Rengar


def restart(rengar=None):
    api = rengar or Rengar()
    response = api.lcu_request("POST", "/riotclient/kill-and-restart-ux", "")
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f"Could not restart Client UX (HTTP {response.status_code})")
