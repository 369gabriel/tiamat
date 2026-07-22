from Rengar import Rengar


DODGE_ENDPOINT = (
    "/lol-login/v1/session/invoke?destination=lcdsServiceProxy&method=call&"
    'args=["","teambuilder-draft","quitV2",""]'
)
DODGE_REQUEST_COUNT = 5


def dodge(rengar=None):
    api = rengar or Rengar()
    last_status = None
    succeeded = False
    for _ in range(DODGE_REQUEST_COUNT):
        response = api.lcu_request("POST", DODGE_ENDPOINT, "")
        last_status = response.status_code
        if 200 <= response.status_code < 300:
            succeeded = True
    if succeeded:
        return
    raise RuntimeError(f"Could not dodge champion select (HTTP {last_status})")
