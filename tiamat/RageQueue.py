import time

from Config import load_config, save_config
from Rengar import Rengar


class RageQueue:
    QUEUE_TYPES = {
        1: ("Normal Draft Pick", 400),
        2: ("Ranked Solo/Duo", 420),
        3: ("Ranked Flex", 440),
        4: ("ARAM", 450),
        5: ("Swiftplay", 480),
        6: ("Quickplay", 490),
        7: ("TFT Normal", 1090),
        8: ("TFT Ranked", 1100),
        9: ("TFT Hyper Roll", 1130),
        10: ("TFT Double Up", 1160),
    }
    POSITION_TYPES = {
        1: ("Top", "TOP"),
        2: ("Jungle", "JUNGLE"),
        3: ("Mid", "MIDDLE"),
        4: ("Bottom", "BOTTOM"),
        5: ("Support", "UTILITY"),
        6: ("Fill", "FILL"),
    }
    DEFAULT_QUEUE_ID = 420
    POSITIONLESS_QUEUE_IDS = {450, 1090, 1100, 1130, 1160}

    def __init__(self, config=None, on_event=None):
        self.config = config if config is not None else load_config()
        settings = self.config.setdefault(
            "ragequeue",
            {"enabled": False, "queue_id": self.DEFAULT_QUEUE_ID},
        )
        self.enabled = bool(settings.get("enabled"))
        self.queue_id = settings.get("queue_id", self.DEFAULT_QUEUE_ID)
        if self.queue_id not in self.queue_names:
            self.queue_id = self.DEFAULT_QUEUE_ID
        self.first_position = settings.get("first_position")
        self.second_position = settings.get("second_position")
        if self.first_position not in self.position_names:
            self.first_position = None
        if self.second_position not in self.position_names:
            self.second_position = None
        self.rengar = Rengar()
        self._armed = False
        self._waiting_for_lobby = False
        self._start_requested = self.enabled
        self._last_phase = None
        self.on_event = on_event or (lambda _level, _message: None)
        self._running = True

    @property
    def queue_names(self):
        return {queue_id: name for name, queue_id in self.QUEUE_TYPES.values()}

    @property
    def queue_name(self):
        return self.queue_names[self.queue_id]

    @property
    def position_names(self):
        return {position: name for name, position in self.POSITION_TYPES.values()}

    @property
    def positions_name(self):
        if not self.requires_positions(self.queue_id):
            return "Not used"
        if not self.first_position or not self.second_position:
            return "Not configured"
        return (
            f"{self.position_names[self.first_position]} / "
            f"{self.position_names[self.second_position]}"
        )

    @classmethod
    def requires_positions(cls, queue_id):
        return queue_id not in cls.POSITIONLESS_QUEUE_IDS

    def set_queue(self, queue_id):
        if queue_id not in self.queue_names:
            raise ValueError("Unsupported queue ID")

        self.queue_id = queue_id
        self.enabled = True
        self._start_requested = True
        self._save_settings()
        self.on_event("success", f"Ragequeue configured for {self.queue_name}")

    def configure(self, queue_id, first_position, second_position):
        if queue_id not in self.queue_names:
            raise ValueError("Unsupported queue ID")
        if first_position not in self.position_names:
            raise ValueError("Unsupported first position")
        if second_position not in self.position_names:
            raise ValueError("Unsupported second position")
        if first_position == second_position:
            raise ValueError("First and second positions must be different")

        self.queue_id = queue_id
        self.first_position = first_position
        self.second_position = second_position
        self.enabled = True
        self._start_requested = True
        self._save_settings()
        self.on_event("success", f"Ragequeue configured for {self.queue_name}")

    def disable(self):
        self.enabled = False
        self._armed = False
        self._waiting_for_lobby = False
        self._start_requested = False
        self._last_phase = None
        self._save_settings()
        self.on_event("info", "Ragequeue disabled")

    def _save_settings(self):
        self.config["ragequeue"] = {
            "enabled": self.enabled,
            "queue_id": self.queue_id,
            "first_position": self.first_position,
            "second_position": self.second_position,
        }
        save_config(self.config)

    @staticmethod
    def _ensure_success(response, action):
        if not 200 <= response.status_code < 300:
            raise RuntimeError(f"Could not {action} (HTTP {response.status_code})")

    def start_queue(self):
        lobby_response = self.rengar.lcu_request(
            "POST",
            "/lol-lobby/v2/lobby",
            {"queueId": self.queue_id},
        )
        self._ensure_success(lobby_response, "create the lobby")

        self.apply_positions_if_unset()

        search_response = self.rengar.lcu_request(
            "POST",
            "/lol-lobby/v2/lobby/matchmaking/search",
            "",
        )
        self._ensure_success(search_response, "start matchmaking")

    def apply_positions_if_unset(self):
        if not self.requires_positions(self.queue_id):
            return
        if not self.first_position or not self.second_position:
            return

        lobby_response = self.rengar.lcu_request(
            "GET", "/lol-lobby/v2/lobby", ""
        )
        self._ensure_success(lobby_response, "read lobby positions")
        local_member = (lobby_response.json() or {}).get("localMember")
        if not isinstance(local_member, dict):
            return

        unset_values = {None, "", "UNSELECTED"}
        first_position = local_member.get("firstPositionPreference")
        second_position = local_member.get("secondPositionPreference")
        if first_position not in unset_values or second_position not in unset_values:
            return

        position_response = self.rengar.lcu_request(
            "PUT",
            "/lol-lobby/v2/lobby/members/localMember/position-preferences",
            {
                "firstPreference": self.first_position,
                "secondPreference": self.second_position,
            },
        )
        self._ensure_success(position_response, "set lobby positions")

    def return_to_lobby(self):
        response = self.rengar.lcu_request(
            "POST", "/lol-lobby/v2/play-again", ""
        )
        self._ensure_success(response, "return to the lobby")

    def check_gameflow(self):
        response = self.rengar.lcu_request(
            "GET", "/lol-gameflow/v1/gameflow-phase", ""
        )
        if response.status_code != 200:
            return

        phase = response.json()
        previous_phase = self._last_phase
        self._last_phase = phase
        if phase == "None" and previous_phase in {"Lobby", "Matchmaking"}:
            self._start_requested = True

        if phase == "InProgress":
            self._armed = True
            self._waiting_for_lobby = False
            self._start_requested = False
        elif phase in {"Matchmaking", "ReadyCheck", "ChampSelect", "GameStart", "Reconnect"}:
            self._start_requested = False
        elif phase == "EndOfGame" and (self._armed or self._start_requested):
            self.return_to_lobby()
            self._armed = False
            self._waiting_for_lobby = True
        elif phase in {"None", "Lobby"} and (
            self._armed or self._waiting_for_lobby or self._start_requested
        ):
            self.start_queue()
            self._armed = False
            self._waiting_for_lobby = False
            self._start_requested = False

    def monitor_gameflow(self):
        while self._running:
            if self.enabled:
                try:
                    self.check_gameflow()
                except Exception as error:
                    self.on_event("error", f"Ragequeue monitor: {error}")

            time.sleep(1)

    def stop(self):
        self._running = False
