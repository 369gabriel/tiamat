from Rengar import get_shared_rengar


def dodge():
    get_shared_rengar().lcu_request(
        "POST",
        '/lol-login/v1/session/invoke?destination=lcdsServiceProxy&method=call&args=["","teambuilder-draft","quitV2",""]',
        "",
    )
