import time
from Config import load_config, save_config
from Rengar import Rengar


class AutoAccept:
    def __init__(self, config=None, on_event=None):
        self.config = config if config is not None else load_config()
        self.auto_accept_enabled = bool(self.config["auto_accept"].get("enabled"))
        self.rengar = Rengar()
        self.on_event = on_event or (lambda _level, _message: None)
        self._running = True

    def toggle_auto_accept(self):
        self.auto_accept_enabled = not self.auto_accept_enabled
        self.config["auto_accept"]["enabled"] = self.auto_accept_enabled
        save_config(self.config)
        state = "activado" if self.auto_accept_enabled else "desactivado"
        self.on_event("info", f"Autoaceptar {state}")
        return self.auto_accept_enabled

    def accept_match(self):
        response = self.rengar.lcu_request(
            "POST", "/lol-matchmaking/v1/ready-check/accept", ""
        )
        if not 200 <= response.status_code < 300:
            raise RuntimeError(f"No se pudo aceptar la partida (HTTP {response.status_code})")
        self.on_event("success", "Partida aceptada")

    def monitor_queue(self):
        while self._running:
            if self.auto_accept_enabled:
                try:
                    response = self.rengar.lcu_request(
                        "GET", "/lol-lobby/v2/lobby/matchmaking/search-state", ""
                    )

                    if response.status_code == 200:
                        match_data = response.json()

                        if match_data.get("searchState") == "Found":
                            self.accept_match()
                except Exception as error:
                    self.on_event("error", f"Monitor de autoaceptar: {error}")

            time.sleep(0.5)

    def stop(self):
        self._running = False
