import base64
import threading
from time import sleep

import psutil
import requests
import urllib3

REQUEST_TIMEOUT = 3
PROCESS_SCAN_SLEEP = 0.5
LEAGUE_CLIENT_PROCESS = "LeagueClientUx.exe"

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_shared_rengar = None
_shared_rengar_lock = threading.Lock()


def _iter_league_client_cmdlines():
    for proc in psutil.process_iter(["name", "cmdline"]):
        try:
            name = proc.info.get("name") or ""
            cmdline = proc.info.get("cmdline") or []
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

        if name != LEAGUE_CLIENT_PROCESS:
            continue

        yield cmdline


def _extract_argument(cmdline, prefix):
    for arg in cmdline:
        if arg.startswith(prefix):
            return arg.split("=", 1)[1]
    return None


def find_league_client_credentials():
    for cmdline in _iter_league_client_cmdlines():
        port = _extract_argument(cmdline, "--app-port=")
        token = _extract_argument(cmdline, "--remoting-auth-token=")
        if port and token:
            return port, token
    return None, None


def check_league_client():
    while True:
        port_check, token_check = find_league_client_credentials()
        if port_check is None and token_check is None:
            sleep(PROCESS_SCAN_SLEEP)
            continue
        return port_check, token_check


def find_riot_client_credentials():
    for cmdline in _iter_league_client_cmdlines():
        port = _extract_argument(cmdline, "--riotclient-app-port=")
        token = _extract_argument(cmdline, "--riotclient-auth-token=")
        if port and token:
            return port, token
    return None, None


def return_lcu_url(league_port):
    return f"https://127.0.0.1:{league_port}"


def return_riot_url(riot_port):
    return f"https://127.0.0.1:{riot_port}"


def return_riot_headers(riot_token):
    auth = base64.b64encode(f"riot:{riot_token}".encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}


def return_lcu_headers(league_token):
    auth = base64.b64encode(f"riot:{league_token}".encode("utf-8")).decode(
        "utf-8"
    )
    return {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}


def get_shared_rengar():
    global _shared_rengar

    with _shared_rengar_lock:
        if _shared_rengar is None:
            _shared_rengar = Rengar()
        return _shared_rengar


class Rengar:
    _credentials_lock = threading.Lock()
    _league_credentials = None
    _riot_credentials = None

    def __init__(self):
        self.league_session = requests.Session()
        self.riot_session = requests.Session()
        self.leaguePort = None
        self.leagueToken = None
        self.leagueUrl = None
        self.leagueHeaders = None
        self.riotPort = None
        self.riotToken = None
        self.riotUrl = None
        self.riotHeaders = None
        self.update_league_credentials()
        self.update_riot_credentials()

    def update_league_credentials(self, force=False):
        with self._credentials_lock:
            if force or self.__class__._league_credentials is None:
                port, token = find_league_client_credentials()
                if port is None or token is None:
                    port, token = check_league_client()
                self.__class__._league_credentials = (port, token)

            self.leaguePort, self.leagueToken = self.__class__._league_credentials

        self.leagueUrl = return_lcu_url(self.leaguePort)
        self.leagueHeaders = return_lcu_headers(self.leagueToken)

    def update_riot_credentials(self, force=False):
        with self._credentials_lock:
            if force or self.__class__._riot_credentials is None:
                port, token = find_riot_client_credentials()
                while port is None or token is None:
                    check_league_client()
                    port, token = find_riot_client_credentials()
                self.__class__._riot_credentials = (port, token)

            self.riotPort, self.riotToken = self.__class__._riot_credentials

        self.riotUrl = return_riot_url(self.riotPort)
        self.riotHeaders = return_riot_headers(self.riotToken)

    def return_lcu_creds(self):
        return self.leaguePort, self.leagueToken, self.leagueUrl

    def return_riot_creds(self):
        return self.riotPort, self.riotToken, self.riotUrl

    def _request(self, session, updater, url, headers, method, endpoint, body):
        payload = None if body in ("", None) else body
        last_error = None

        for attempt in range(2):
            if attempt:
                updater(force=True)

            try:
                return session.request(
                    method=method.upper(),
                    url=f"{getattr(self, url)}{endpoint}",
                    headers=getattr(self, headers),
                    json=payload,
                    verify=False,
                    timeout=REQUEST_TIMEOUT,
                )
            except requests.exceptions.RequestException as exc:
                last_error = exc
                check_league_client()

        raise last_error

    def lcu_request(self, method, endpoint, body):
        return self._request(
            session=self.league_session,
            updater=self.update_league_credentials,
            url="leagueUrl",
            headers="leagueHeaders",
            method=method,
            endpoint=endpoint,
            body=body,
        )

    def riot_request(self, method, endpoint, body):
        return self._request(
            session=self.riot_session,
            updater=self.update_riot_credentials,
            url="riotUrl",
            headers="riotHeaders",
            method=method,
            endpoint=endpoint,
            body=body,
        )
