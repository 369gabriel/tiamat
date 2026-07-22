from Rengar import Rengar


class Chat:
    def __init__(self, rengar=None, read_state=True):
        self.rengar = rengar or Rengar()
        self.chat_state = self.return_disconnect() if read_state else False

    def return_disconnect(self):
        response = self.rengar.riot_request("GET", "/chat/v1/session", "")
        if response.status_code != 200:
            raise RuntimeError(f"Could not read chat state (HTTP {response.status_code})")
        return response.json().get("state") == "disconnected"

    def disconnect(self):
        response = self.rengar.riot_request(
            "POST", "/chat/v1/suspend", {"config": "disable"}
        )
        if not 200 <= response.status_code < 300:
            raise RuntimeError(f"Could not disconnect chat (HTTP {response.status_code})")
        self.chat_state = True

    def reconnect(self):
        response = self.rengar.riot_request("POST", "/chat/v1/resume", "")
        if not 200 <= response.status_code < 300:
            raise RuntimeError(f"Could not reconnect chat (HTTP {response.status_code})")
        self.chat_state = False

    def toggle_chat(self):
        if self.chat_state:
            self.reconnect()
        else:
            self.disconnect()
        return self.chat_state

    def return_state(self):
        return "OFFLINE" if self.chat_state else "LIVE"
