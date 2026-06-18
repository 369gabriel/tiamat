import time
import random
from Rengar import Rengar


class InstalockAutoban:
    def __init__(self):
        self.champ_dict = {}
        self.instalock_enabled = False
        self.instalock_champion = "Random"
        self.auto_ban_enabled = False
        self.auto_ban_champion = "None"
        self.rengar = Rengar()

    def update_champion_list(self):
        response = self.rengar.lcu_request("GET", "/lol-champ-select/v1/all-grid-champions", "")

        if response.status_code == 200:
            champion_data = response.json()
            for champ in champion_data:
                champ_id = champ["id"]
                champ_name = champ["name"]
                self.champ_dict[champ_name.lower()] = champ_id
        else:
            print("Failed to fetch champion data.")

    def champ_name_to_id(self, champ_name):
        return self.champ_dict.get(champ_name.lower(), -1)

    def set_instalock_champion(self, champion_name):
        if champion_name == "99":
            self.instalock_enabled = False
            self.instalock_champion = "None"
        else:
            if not self.champ_dict:
                self.update_champion_list()
            champ_id = self.champ_name_to_id(champion_name)
            if champ_id == -1:
                print(f"Champion '{champion_name}' not found.")
            else:
                self.instalock_champion = champion_name
                self.instalock_enabled = True

    def set_auto_ban_champion(self, champion_name):
        if champion_name == "99":
            self.auto_ban_enabled = False
            self.auto_ban_champion = "None"
        else:
            if not self.champ_dict:
                self.update_champion_list()
            champ_id = self.champ_name_to_id(champion_name)
            if champ_id == -1:
                print(f"Champion '{champion_name}' not found.")
            else:
                self.auto_ban_champion = champion_name
                self.auto_ban_enabled = True

    def monitor_champ_select(self):
        while True:
            try:
                if not self.champ_dict:
                    self.update_champion_list()

                champ_select_resp = self.rengar.lcu_request(
                    "GET", "/lol-champ-select/v1/session", ""
                )
                if "RPC_ERROR" not in champ_select_resp.text:
                    root_champ_select = champ_select_resp.json()
                    cell_id = root_champ_select.get("localPlayerCellId")

                    if cell_id is None:
                        time.sleep(0.3)
                        continue

                    for actions in root_champ_select["actions"]:
                        if not isinstance(actions, list):
                            continue
                        for action in actions:
                            if (
                                self.instalock_enabled
                                and action["actorCellId"] == cell_id
                                and action["type"] == "pick"
                                and not action["completed"]
                            ):
                                time.sleep(0.3)

                                if self.instalock_champion == "Random":
                                    champion_id = random.choice(list(self.champ_dict.items()))[1]
                                else:
                                    champion_id = self.champ_name_to_id(self.instalock_champion)

                                self.rengar.lcu_request(
                                    "PATCH",
                                    f"/lol-champ-select/v1/session/actions/{action['id']}",
                                    {"completed": True, "championId": champion_id},
                                )

                                time.sleep(0.3)

                            elif (
                                self.auto_ban_enabled
                                and action["actorCellId"] == cell_id
                                and action["type"] == "ban"
                                and not action["completed"]
                            ):
                                time.sleep(0.3)
                                champion_id = self.champ_name_to_id(self.auto_ban_champion)

                                self.rengar.lcu_request(
                                    "PATCH",
                                    f"/lol-champ-select/v1/session/actions/{action['id']}",
                                    {"completed": True, "championId": champion_id},
                                )

                                continue

                time.sleep(0.3)
            except Exception as e:
                print(f"Champion select monitor error: {e}")
                time.sleep(1)

    def toggle_instalock(self):
        self.instalock_enabled = not self.instalock_enabled

    def toggle_auto_ban(self):
        self.auto_ban_enabled = not self.auto_ban_enabled
