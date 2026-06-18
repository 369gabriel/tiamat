from Rengar import Rengar

def restart():
	rengar = Rengar()
	rengar.lcu_request("POST", '/riotclient/kill-and-restart-ux','')
