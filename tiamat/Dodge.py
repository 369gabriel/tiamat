from Rengar import Rengar


DODGE_ENDPOINT = (
    "/lol-login/v1/session/invoke?destination=lcdsServiceProxy&method=call&"
    'args=["","teambuilder-draft","quitV2",""]'
)


def dodge(rengar=None):
    api = rengar or Rengar()
    last_status = None
    for _ in range(6):
        response = api.lcu_request("POST", DODGE_ENDPOINT, "")
        last_status = response.status_code
        if 200 <= response.status_code < 300:
            return
    raise RuntimeError(f"Could not dodge champion select (HTTP {last_status})")
