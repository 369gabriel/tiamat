from Rengar import Rengar


DODGE_ENDPOINT = (
    "/lol-login/v1/session/invoke?destination=lcdsServiceProxy&method=call&"
    'args=["","teambuilder-draft","quitV2",""]'
)
DODGE_REQUEST_COUNT = 5


def dodge(rengar=None):
    api = rengar or Rengar()
    last_status = None
    last_error = None
    succeeded = False
    for _ in range(DODGE_REQUEST_COUNT):
        try:
            response = api.lcu_request("POST", DODGE_ENDPOINT, "")
        except Exception as error:
            last_error = error
            continue
        last_status = response.status_code
        if 200 <= response.status_code < 300:
            succeeded = True
    if succeeded:
        return
    if last_status is None and last_error is not None:
        raise RuntimeError(f"Could not dodge champion select ({last_error})")
    raise RuntimeError(f"Could not dodge champion select (HTTP {last_status})")
