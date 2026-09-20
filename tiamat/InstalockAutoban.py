import time
import random
from Config import get_automation_delay, load_config, save_config
from Rengar import Rengar


class InstalockAutoban:
    def __init__(self, config=None, on_event=None):
        self.config = config if config is not None else load_config()
        self.champ_dict = {}
        self.instalock_enabled = bool(self.config["instalock"].get("enabled"))
        self.instalock_champion = self.config["instalock"].get("champion", "Random")
        self.fallback_champion = self.config["instalock"].get("fallback_champion") or None
        self.auto_ban_enabled = bool(self.config["autoban"].get("enabled"))
        self.auto_ban_champion = self.config["autoban"].get("champion", "None")
        self.rengar = Rengar()
        self.on_event = on_event or (lambda _level, _message: None)
        self._running = True

    def save_settings(self):
        self.config["instalock"]["enabled"] = self.instalock_enabled
        self.config["instalock"]["champion"] = self.instalock_champion
        self.config["instalock"]["fallback_champion"] = self.fallback_champion
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
                    normalized_name = champ_name.lower()
                    current_id = self.champ_dict.get(normalized_name)
                    if current_id is None or champ_id < current_id:
                        self.champ_dict[normalized_name] = champ_id
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

    def configure_instalock(self, champion, fallback=None):
        if not self.champ_dict:
            self.update_champion_list()
        if champion.lower() != "random" and self.champ_name_to_id(champion) == -1:
            raise ValueError(f"Champion '{champion}' was not found")
        if fallback and self.champ_name_to_id(fallback) == -1:
            raise ValueError(f"Fallback champion '{fallback}' was not found")
        if fallback and champion.lower() == fallback.lower():
            raise ValueError("Choose a different fallback champion")
        self.instalock_champion = "Random" if champion.lower() == "random" else champion
        self.fallback_champion = fallback or None
        self.instalock_enabled = True
        self.save_settings()
        message = f"Instalock configured for {self.instalock_champion}"
        if self.fallback_champion:
            message += f" (fallback: {self.fallback_champion})"
        self.on_event("success", message)

    def choose_pick(self, session):
        response = self.rengar.lcu_request(
            "GET", "/lol-champ-select/v1/pickable-champion-ids", ""
        )
        if response.status_code != 200:
            raise RuntimeError(f"Could not check available champions (HTTP {response.status_code})")
        pickable = response.json()
        if not isinstance(pickable, list):
            raise RuntimeError("Could not read available champions")
        available = set(pickable)
        bans = session.get("bans") or {}
        available.difference_update(bans.get("myTeamBans", []), bans.get("theirTeamBans", []))
        teams = list(session.get("myTeam", []))
        if not session.get("allowDuplicatePicks", False):
            teams += session.get("theirTeam", [])
        # A hover is not a completed pick and must not trigger the fallback.
        completed_picks = {
            action.get("actorCellId")
            for group in session.get("actions", []) for action in group
            if action.get("type") == "pick" and action.get("completed")
        }
        available.difference_update(
            player.get("championId") for player in teams
            if player.get("cellId") in completed_picks
        )
        available.difference_update(
            action.get("championId")
            for group in session.get("actions", []) for action in group
            if action.get("type") == "ban" and action.get("completed")
        )
        if self.instalock_champion == "Random":
            choices = [(name.title(), champion_id) for name, champion_id in self.champ_dict.items()
                       if champion_id in available]
            if choices:
                name, champion_id = random.choice(choices)
                return champion_id, name
        else:
            champion_id = self.champ_name_to_id(self.instalock_champion)
            if champion_id in available:
                return champion_id, self.instalock_champion
        if self.fallback_champion:
            champion_id = self.champ_name_to_id(self.fallback_champion)
            if champion_id in available:
                return champion_id, self.fallback_champion
        self.on_event("warning", "No configured champion is available; choose a champion manually")
        return None

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
                                and action.get("isInProgress", False)
                            ):
                                delay = get_automation_delay(
                                    self.config, "instalock", 0.3
                                )
                                if delay:
                                    time.sleep(delay)

                                refreshed = self.rengar.lcu_request(
                                    "GET", "/lol-champ-select/v1/session", ""
                                )
                                if refreshed.status_code != 200:
                                    continue
                                session = refreshed.json()
                                current_action = next((
                                    item for group in session.get("actions", []) for item in group
                                    if item.get("id") == action["id"]
                                ), None)
                                if not current_action or current_action.get("completed") or not current_action.get("isInProgress"):
                                    continue
                                pick = self.choose_pick(session)
                                if pick is None:
                                    continue
                                champion_id, champion_name = pick

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
                                    f"Locked {champion_name}",
                                )

                                time.sleep(0.3)

                            elif (
                                self.auto_ban_enabled
                                and action["actorCellId"] == cell_id
                                and action["type"] == "ban"
                                and not action["completed"]
                            ):
                                delay = get_automation_delay(
                                    self.config, "autoban", 0.3
                                )
                                if delay:
                                    time.sleep(delay)
                                champion_id = self.champ_name_to_id(self.auto_ban_champion)
                                action_endpoint = (
                                    "/lol-champ-select/v1/session/actions/"
                                    f"{action['id']}"
                                )

                                response = self.rengar.lcu_request(
                                    "PATCH",
                                    action_endpoint,
                                    {"completed": True, "championId": champion_id},
                                )
                                if not 200 <= response.status_code < 300:
                                    raise RuntimeError(
                                        f"Could not ban champion (HTTP {response.status_code})"
                                    )

                                verification = self.rengar.lcu_request(
                                    "GET", "/lol-champ-select/v1/session", ""
                                )
                                if verification.status_code == 200:
                                    verified_session = verification.json()
                                    verified_action = next(
                                        (
                                            current_action
                                            for action_group in verified_session.get(
                                                "actions", []
                                            )
                                            for current_action in action_group
                                            if current_action.get("id") == action["id"]
                                        ),
                                        None,
                                    )
                                    if (
                                        verified_action
                                        and verified_action.get("completed")
                                        and verified_action.get("championId") == champion_id
                                    ):
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
