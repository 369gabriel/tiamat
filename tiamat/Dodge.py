from Rengar import Rengar

def dodge():
	rengar = Rengar()
	rengar.lcu_request("POST", '/lol-login/v1/session/invoke?destination=lcdsServiceProxy&method=call&args=["","teambuilder-draft","quitV2",""]', "")
