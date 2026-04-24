from Rengar import get_shared_rengar


class Chat:
    def __init__(self):
        self.rengar = get_shared_rengar()
        self.chat_state = False

    def return_disconnect(self):
        try:
            req = self.rengar.riot_request("GET", "/chat/v1/session", "")
            if req.status_code != 200:
                return self.chat_state

            req_data = req.json()
            self.chat_state = req_data.get("state") == "disconnected"
        except Exception:
            return self.chat_state

        return self.chat_state

    def disconnect(self):
        body = {"config": "disable"}
        response = self.rengar.riot_request("POST", "/chat/v1/suspend", body)
        if response.status_code in (200, 204):
            self.chat_state = True
        print(response.text)

    def reconnect(self):
        response = self.rengar.riot_request("POST", "/chat/v1/resume", "")
        if response.status_code in (200, 204):
            self.chat_state = False

    def toggle_chat(self):
        if self.return_disconnect():
            self.reconnect()
        else:
            self.disconnect()

    def return_state(self):
        return "ON" if self.chat_state else "OFF"
