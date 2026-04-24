import threading
import time

from Rengar import get_shared_rengar


class autoaccept:
    def __init__(self):
        self.auto_accept_enabled = False
        self.rengar = get_shared_rengar()
        self._monitor_started = False
        self._monitor_lock = threading.Lock()

    def ensure_monitor_started(self):
        with self._monitor_lock:
            if self._monitor_started:
                return

            threading.Thread(target=self.monitor_queue, daemon=True).start()
            self._monitor_started = True

    def toggle_auto_accept(self):
        self.ensure_monitor_started()
        self.auto_accept_enabled = not self.auto_accept_enabled
        state = "ON" if self.auto_accept_enabled else "OFF"
        print(f"Auto accept is now {state}.")

    def accept_match(self):
        self.rengar.lcu_request("POST", "/lol-matchmaking/v1/ready-check/accept", "")

    def monitor_queue(self):
        while True:
            if not self.auto_accept_enabled:
                time.sleep(1)
                continue

            try:
                response = self.rengar.lcu_request(
                    "GET", "/lol-lobby/v2/lobby/matchmaking/search-state", ""
                )

                if response.status_code == 200:
                    match_data = response.json()
                    if match_data.get("searchState") == "Found":
                        self.accept_match()
            except Exception:
                time.sleep(1)
                continue

            time.sleep(0.5)
