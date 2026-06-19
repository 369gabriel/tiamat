import time
from Config import load_config, save_config
from Rengar import Rengar


class AutoAccept:
    def __init__(self, config=None):
        self.config = config if config is not None else load_config()
        self.auto_accept_enabled = bool(self.config["auto_accept"].get("enabled"))
        self.rengar = Rengar()

    def toggle_auto_accept(self):
        self.auto_accept_enabled = not self.auto_accept_enabled
        self.config["auto_accept"]["enabled"] = self.auto_accept_enabled
        save_config(self.config)
        state = "ON" if self.auto_accept_enabled else "OFF"
        print(f"Auto accept is now {state}.")

    def accept_match(self):
        self.rengar.lcu_request("POST", "/lol-matchmaking/v1/ready-check/accept", "")

    def monitor_queue(self):
        while True:
            if self.auto_accept_enabled:
                response = self.rengar.lcu_request(
                    "GET", "/lol-lobby/v2/lobby/matchmaking/search-state", ""
                )

                if response.status_code == 200:
                    match_data = response.json()

                    if match_data.get("searchState") == "Found":
                        self.accept_match()

            time.sleep(0.5)
