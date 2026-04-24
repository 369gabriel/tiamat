import random
import threading
import time

from Rengar import get_shared_rengar


class InstalockAutoban:
    def __init__(self):
        self.champ_dict = {}
        self.instalock_enabled = False
        self.instalock_champion = "Random"
        self.auto_ban_enabled = False
        self.auto_ban_champion = "None"
        self.rengar = get_shared_rengar()
        self._champions_loaded = False
        self._monitor_started = False
        self._monitor_lock = threading.Lock()

    def ensure_monitor_started(self):
        with self._monitor_lock:
            if self._monitor_started:
                return

            threading.Thread(target=self.monitor_champ_select, daemon=True).start()
            self._monitor_started = True

    def update_champion_list(self, force=False):
        if self._champions_loaded and not force:
            return True

        response = self.rengar.lcu_request(
            "GET", "/lol-champ-select/v1/all-grid-champions", ""
        )

        if response.status_code != 200:
            print("Failed to fetch champion data.")
            return False

        champion_data = response.json()
        self.champ_dict = {
            champ["name"].lower(): champ["id"] for champ in champion_data
        }
        self._champions_loaded = True
        return True

    def champ_name_to_id(self, champ_name):
        if not self._champions_loaded and not self.update_champion_list():
            return -1

        return self.champ_dict.get(champ_name.lower(), -1)

    def _resolve_instalock_champion_id(self):
        if self.instalock_champion == "Random":
            if not self._champions_loaded and not self.update_champion_list():
                return -1

            instalock_champs = list(self.champ_dict.values())
            if not instalock_champs:
                return -1
            return random.choice(instalock_champs)

        return self.champ_name_to_id(self.instalock_champion)

    def set_instalock_champion(self, champion_name):
        champion_name = champion_name.strip()
        if champion_name == "99":
            self.instalock_enabled = False
            self.instalock_champion = "None"
            return

        if champion_name.lower() == "random":
            self.instalock_champion = "Random"
            self.instalock_enabled = True
            self.ensure_monitor_started()
            return

        champ_id = self.champ_name_to_id(champion_name)
        if champ_id == -1:
            print(f"Champion '{champion_name}' not found.")
            return

        self.instalock_champion = champion_name
        self.instalock_enabled = True
        self.ensure_monitor_started()

    def set_auto_ban_champion(self, champion_name):
        champion_name = champion_name.strip()
        if champion_name == "99":
            self.auto_ban_enabled = False
            self.auto_ban_champion = "None"
            return

        champ_id = self.champ_name_to_id(champion_name)
        if champ_id == -1:
            print(f"Champion '{champion_name}' not found.")
            return

        self.auto_ban_champion = champion_name
        self.auto_ban_enabled = True
        self.ensure_monitor_started()

    def monitor_champ_select(self):
        while True:
            if not self.instalock_enabled and not self.auto_ban_enabled:
                time.sleep(1)
                continue

            try:
                champ_select_resp = self.rengar.lcu_request(
                    "GET", "/lol-champ-select/v1/session", ""
                )
                if champ_select_resp.status_code != 200:
                    time.sleep(1)
                    continue

                if "RPC_ERROR" in champ_select_resp.text:
                    time.sleep(1)
                    continue

                root_champ_select = champ_select_resp.json()
                cell_id = root_champ_select.get("localPlayerCellId")
                if cell_id is None:
                    time.sleep(0.75)
                    continue

                for actions in root_champ_select.get("actions", []):
                    if not isinstance(actions, list):
                        continue

                    for action in actions:
                        if action.get("actorCellId") != cell_id or action.get(
                            "completed"
                        ):
                            continue

                        if self.instalock_enabled and action.get("type") == "pick":
                            champion_id = self._resolve_instalock_champion_id()
                            if champion_id == -1:
                                continue

                            self.rengar.lcu_request(
                                "PATCH",
                                f"/lol-champ-select/v1/session/actions/{action['id']}",
                                {"completed": True, "championId": champion_id},
                            )
                            time.sleep(0.25)
                        elif self.auto_ban_enabled and action.get("type") == "ban":
                            champion_id = self.champ_name_to_id(self.auto_ban_champion)
                            if champion_id == -1:
                                continue

                            self.rengar.lcu_request(
                                "PATCH",
                                f"/lol-champ-select/v1/session/actions/{action['id']}",
                                {"completed": True, "championId": champion_id},
                            )
                            time.sleep(0.25)
            except Exception:
                time.sleep(1)
                continue

            time.sleep(0.5)

    def toggle_instalock(self):
        self.ensure_monitor_started()
        self.instalock_enabled = not self.instalock_enabled

    def toggle_auto_ban(self):
        self.ensure_monitor_started()
        self.auto_ban_enabled = not self.auto_ban_enabled
