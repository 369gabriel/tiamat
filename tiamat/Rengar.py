import base64
import json
import os
import re
from pathlib import Path
from time import sleep

import psutil
import requests
import urllib3

urllib3.disable_warnings()

REQUEST_TIMEOUT_SECONDS = 5
REQUEST_RETRIES = 2


LEAGUE_CLIENT_UX = "LeagueClientUx"
DARLING_LOCKFILE = Path("Applications/League of Legends.app/Contents/LoL/lockfile")


def _is_league_client_ux(info):
    # Under Darling (macOS client on Linux) the process name is a thread name
    # like "CrBrowserMain", so the executable path in argv[0] is checked too.
    # argv[0] may itself contain spaces ("League of Legends.app"), so take
    # everything before the first flag as the executable path.
    name = info.get("name") or ""
    executable_path = " ".join(info.get("cmdline") or []).split(" --", 1)[0]
    executable = os.path.basename(executable_path)
    return name.startswith(LEAGUE_CLIENT_UX) or executable.startswith(LEAGUE_CLIENT_UX)


def _find_arg(cmdline, flag):
    # Darling may expose argv as one space-joined string, so search the whole line.
    match = re.search(rf"(?:^|\s){re.escape(flag)}=(\S+)", " ".join(cmdline))
    return match.group(1) if match else None


def _league_client_ux_cmdlines():
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        if _is_league_client_ux(proc.info):
            yield proc.info.get("cmdline") or []


def _find_client_ux_credentials(cmdlines, port_flag, token_flag):
    for cmdline in cmdlines:
        port = _find_arg(cmdline, port_flag)
        token = _find_arg(cmdline, token_flag)
        if port and token:
            return port, token

    return None, None


def _darling_lockfile_paths():
    prefixes = [os.environ.get("DPREFIX"), Path.home() / ".darling"]
    return [Path(prefix) / DARLING_LOCKFILE for prefix in prefixes if prefix]


def _read_lockfile_credentials():
    # Lockfile format: name:pid:port:password:protocol
    for path in _darling_lockfile_paths():
        try:
            fields = path.read_text().strip().split(":")
        except OSError:
            continue
        if len(fields) == 5:
            return fields[2], fields[3]

    return None, None


def find_league_client_credentials():
    cmdlines = list(_league_client_ux_cmdlines())
    port, token = _find_client_ux_credentials(cmdlines, "--app-port", "--remoting-auth-token")
    if port and token:
        return port, token
    # Only trust the lockfile while a client is running; a stale one outlives crashes.
    if cmdlines:
        return _read_lockfile_credentials()
    return None, None


def check_league_client():
    while True:
        port_check, token_check = find_league_client_credentials()
        if port_check and token_check:
            return port_check, token_check
        sleep(0.5)


def find_riot_client_credentials():
    return _find_client_ux_credentials(
        _league_client_ux_cmdlines(), "--riotclient-app-port", "--riotclient-auth-token"
    )


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
