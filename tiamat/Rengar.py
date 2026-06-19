import base64
import json
from time import sleep

import psutil
import requests
import urllib3

urllib3.disable_warnings()

REQUEST_TIMEOUT_SECONDS = 5
REQUEST_RETRIES = 2


def _split_arg(arg, prefix):
    if arg and arg.startswith(prefix):
        return arg.split("=", 1)[1]
    return None


def find_league_client_credentials():
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        info = proc.info
        if info.get("name") != "LeagueClientUx.exe":
            continue

        port = None
        token = None
        for arg in info.get("cmdline") or []:
            port = port or _split_arg(arg, "--app-port=")
            token = token or _split_arg(arg, "--remoting-auth-token=")

        if port and token:
            return port, token

    return None, None


def check_league_client():
    while True:
        port_check, token_check = find_league_client_credentials()
        if port_check and token_check:
            return port_check, token_check
        sleep(0.5)


def find_riot_client_credentials():
    for process in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
        info = process.info
        name = info.get("name") or ""
        if "LeagueClientUx" not in name:
            continue

        port = None
        token = None
        for arg in info.get("cmdline") or []:
            token = token or _split_arg(arg, "--riotclient-auth-token=")
            port = port or _split_arg(arg, "--riotclient-app-port=")

        if port and token:
            return port, token

    return None, None


def return_lcu_url(leaguePort):
    if not leaguePort:
        return None
    return f"https://127.0.0.1:{leaguePort}"


def return_riot_url(riotPort):
    if not riotPort:
        return None
    return f"https://127.0.0.1:{riotPort}"


def _headers(token):
    if not token:
        return {}
    auth = base64.b64encode(f"riot:{token}".encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}


def return_riot_headers(riotToken):
    return _headers(riotToken)


def return_lcu_headers(leagueToken):
    return _headers(leagueToken)


class Rengar:
    def __init__(self):
        self.update_league_credentials()
        self.update_riot_credentials()

    def update_league_credentials(self):
        self.leaguePort, self.leagueToken = find_league_client_credentials()
        self.leagueUrl = return_lcu_url(self.leaguePort)
        self.leagueHeaders = return_lcu_headers(self.leagueToken)

    def update_riot_credentials(self):
        self.riotPort, self.riotToken = find_riot_client_credentials()
        self.riotUrl = return_riot_url(self.riotPort)
        self.riotHeaders = return_riot_headers(self.riotToken)

    def return_lcu_creds(self):
        return self.leaguePort, self.leagueToken, self.leagueUrl

    def return_riot_creds(self):
        return self.riotPort, self.riotToken, self.riotUrl

    def _request(self, method, base_url, headers, endpoint, body, refresh_credentials, service):
        method = method.upper()
        if method not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
            raise ValueError("Invalid method")

        payload = None if body == "" else body
        if payload is not None:
            payload = json.dumps(payload)

        for attempt in range(REQUEST_RETRIES + 1):
            if not base_url:
                check_league_client()
                refresh_credentials()
                base_url, headers = self._service_connection(service)
                if not base_url:
                    raise RuntimeError(f"Could not find {service} client credentials")

            try:
                return requests.request(
                    method,
                    f"{base_url}{endpoint}",
                    headers=headers,
                    data=payload,
                    verify=False,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
            except requests.exceptions.RequestException:
                if attempt == REQUEST_RETRIES:
                    raise
                check_league_client()
                refresh_credentials()
                base_url, headers = self._service_connection(service)

    def _service_connection(self, service):
        if service == "league":
            return self.leagueUrl, self.leagueHeaders
        return self.riotUrl, self.riotHeaders

    def lcu_request(self, method, endpoint, body: dict):
        return self._request(
            method,
            self.leagueUrl,
            self.leagueHeaders,
            endpoint,
            body,
            self.update_league_credentials,
            "league",
        )

    def riot_request(self, method, endpoint, body: dict):
        return self._request(
            method,
            self.riotUrl,
            self.riotHeaders,
            endpoint,
            body,
            self.update_riot_credentials,
            "riot",
        )
