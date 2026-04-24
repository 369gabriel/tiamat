from Rengar import get_shared_rengar


def restart():
    get_shared_rengar().lcu_request("POST", "/riotclient/kill-and-restart-ux", "")
