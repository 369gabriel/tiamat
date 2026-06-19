from Rengar import Rengar


class Chat:
    def __init__(self):
        self.rengar = Rengar()
        self.chat_state = self.return_disconnect()

    def return_disconnect(self):
        req = self.rengar.riot_request("GET", "/chat/v1/session", "")
        req_data = req.json()
        if req_data["state"] == "disconnected":
            return True
        else:
            return False

    def disconnect(self):
        body = {"config": "disable"}
        response = self.rengar.riot_request("POST", "/chat/v1/suspend", body)
        print(response.text)  # Troquei `input` por `print` para exibir a resposta

    def reconnect(self):
        self.rengar.riot_request("POST", "/chat/v1/resume", "")

    def toggle_chat(self):
        self.chat_state = not self.chat_state
        if self.chat_state:
            self.disconnect()
        else:
            self.reconnect()

    def return_state(self):
        if not self.chat_state:
            return "ON"
        else:
            return "OFF"
