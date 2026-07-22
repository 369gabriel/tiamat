import time
import random
from Config import load_config, save_config
from Rengar import Rengar


class InstalockAutoban:
    def __init__(self, config=None, on_event=None):
        self.config = config if config is not None else load_config()
        self.champ_dict = {}
        self.instalock_enabled = bool(self.config["instalock"].get("enabled"))
        self.instalock_champion = self.config["instalock"].get("champion", "Random")
        self.auto_ban_enabled = bool(self.config["autoban"].get("enabled"))
        self.auto_ban_champion = self.config["autoban"].get("champion", "None")
        self.rengar = Rengar()
        self.on_event = on_event or (lambda _level, _message: None)
        self._running = True

    def save_settings(self):
        self.config["instalock"]["enabled"] = self.instalock_enabled
        self.config["instalock"]["champion"] = self.instalock_champion
        self.config["autoban"]["enabled"] = self.auto_ban_enabled
        self.config["autoban"]["champion"] = self.auto_ban_champion
        save_config(self.config)

    def update_champion_list(self):
        response = self.rengar.lcu_request(
            "GET", "/lol-game-data/assets/v1/champion-summary.json", ""
        )

        if response.status_code == 200:
            champion_data = response.json()
            for champ in champion_data:
                champ_id = champ["id"]
                champ_name = champ["name"]
                if champ_id > 0:
                    self.champ_dict[champ_name.lower()] = champ_id
        else:
            raise RuntimeError(f"Could not fetch champion data (HTTP {response.status_code})")
        return sorted(self.champ_dict)

    def champ_name_to_id(self, champ_name):
        return self.champ_dict.get(champ_name.lower(), -1)

    def set_instalock_champion(self, champion_name):
        if champion_name.lower() == "random":
            self.instalock_champion = "Random"
        else:
            if not self.champ_dict:
                self.update_champion_list()
            if self.champ_name_to_id(champion_name) == -1:
                raise ValueError(f"Champion '{champion_name}' was not found")
            self.instalock_champion = champion_name
        self.instalock_enabled = True
        self.save_settings()
        self.on_event("success", f"Instalock configured for {self.instalock_champion}")
        return self.instalock_champion

    def set_auto_ban_champion(self, champion_name):
        if not self.champ_dict:
            self.update_champion_list()
        if self.champ_name_to_id(champion_name) == -1:
            raise ValueError(f"Champion '{champion_name}' was not found")
        self.auto_ban_champion = champion_name
        self.auto_ban_enabled = True
        self.save_settings()
        self.on_event("success", f"AutoBan configured for {self.auto_ban_champion}")
        return self.auto_ban_champion

    def monitor_champ_select(self):
        while self._running:
            try:
                if not self.instalock_enabled and not self.auto_ban_enabled:
                    time.sleep(0.3)
                    continue
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

                                response = self.rengar.lcu_request(
                                    "PATCH",
                                    f"/lol-champ-select/v1/session/actions/{action['id']}",
                                    {"completed": True, "championId": champion_id},
                                )
                                if not 200 <= response.status_code < 300:
                                    raise RuntimeError(
                                        f"Could not lock champion (HTTP {response.status_code})"
                                    )
                                self.on_event(
                                    "success",
                                    f"Locked {self.instalock_champion}",
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

                                response = self.rengar.lcu_request(
                                    "PATCH",
                                    f"/lol-champ-select/v1/session/actions/{action['id']}",
                                    {"completed": True, "championId": champion_id},
                                )
                                if not 200 <= response.status_code < 300:
                                    raise RuntimeError(
                                        f"Could not ban champion (HTTP {response.status_code})"
                                    )
                                self.on_event(
                                    "success",
                                    f"Banned {self.auto_ban_champion}",
                                )

                                continue

                time.sleep(0.3)
            except Exception as error:
                self.on_event("error", f"Champion select monitor: {error}")
                time.sleep(1)

    def toggle_instalock(self):
        self.instalock_enabled = not self.instalock_enabled
        self.save_settings()
        state = "enabled" if self.instalock_enabled else "disabled"
        self.on_event("info", f"Instalock {state}")
        return self.instalock_enabled

    def toggle_auto_ban(self):
        self.auto_ban_enabled = not self.auto_ban_enabled
        self.save_settings()
        state = "enabled" if self.auto_ban_enabled else "disabled"
        self.on_event("info", f"AutoBan {state}")
        return self.auto_ban_enabled

    def stop(self):
        self._running = False
