"""Ranked win/loss records from OP.GG's public MCP endpoint.

The League Client hides other players' losses (it reports 0), so real
winrates come from OP.GG. The endpoint is hosted by OP.GG and needs no key;
it speaks MCP (JSON-RPC over HTTP) and answers in a compact text format.
"""

import ast
import json
import re
import threading

import requests

from version import __version__

MCP_URL = "https://mcp-api.op.gg/mcp"
PROTOCOL_VERSION = "2025-03-26"
REQUEST_TIMEOUT_SECONDS = 8
CLIENT_APP = f"tiamat/{__version__}"

QUEUE_KEYS = {
    "SOLORANKED": "RANKED_SOLO_5x5",
    "FLEXRANKED": "RANKED_FLEX_SR",
}

PROFILE_FIELDS = [
    "data.summoner.league_stats[].{game_type,win,lose}",
]

_CLASS_LINE = re.compile(r"^class (\w+): (.*)$")
_NAMES = {"null": None, "true": True, "false": False}


def parse_compact(text):
    """Parse OP.GG's compact output into plain dicts and lists.

    The text declares field names (``class LeagueStat: game_type,win,lose``)
    followed by one constructor expression using them. It is parsed with
    ``ast`` and converted node by node; nothing is ever evaluated.
    """
    classes = {}
    expression = []
    for line in text.splitlines():
        match = _CLASS_LINE.match(line)
        if match:
            classes[match.group(1)] = [
                field.strip() for field in match.group(2).split(",") if field.strip()
            ]
        elif line.strip():
            expression.append(line)

    def convert(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name) and node.id in _NAMES:
            return _NAMES[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -convert(node.operand)
        if isinstance(node, ast.List):
            return [convert(element) for element in node.elts]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            fields = classes.get(node.func.id)
            values = [convert(argument) for argument in node.args]
            if fields is None or len(values) > len(fields):
                raise ValueError(f"Unexpected OP.GG record {node.func.id}")
            return dict(zip(fields, values))
        raise ValueError(f"Unexpected OP.GG syntax: {type(node).__name__}")

    return convert(ast.parse("\n".join(expression), mode="eval").body)


def records_from_profile(profile):
    """Map ``{queue_key: (wins, losses)}`` from a parsed profile."""
    summoner = ((profile or {}).get("data") or {}).get("summoner") or {}
    records = {}
    for stat in summoner.get("league_stats") or []:
        queue = QUEUE_KEYS.get((stat or {}).get("game_type"))
        wins, losses = (stat or {}).get("win"), (stat or {}).get("lose")
        if queue and isinstance(wins, int) and isinstance(losses, int):
            records[queue] = (wins, losses)
    return records


class OpggClient:
    def __init__(self, url=MCP_URL, post=None):
        self.url = url
        self._post = post or requests.post
        self._session_id = None
        self._lock = threading.RLock()
        self._next_id = 0

    def _headers(self):
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "User-Agent": CLIENT_APP,
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    @staticmethod
    def _parse_body(response):
        if "text/event-stream" in response.headers.get("Content-Type", ""):
            messages = [
                json.loads(line[5:].strip())
                for line in response.text.splitlines()
                if line.startswith("data:")
            ]
            return messages[-1] if messages else None
        return response.json() if response.text.strip() else None

    def _send(self, method, params=None, notify=False):
        body = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        if not notify:
            with self._lock:
                self._next_id += 1
                body["id"] = self._next_id
        response = self._post(
            self.url, json=body, headers=self._headers(), timeout=REQUEST_TIMEOUT_SECONDS
        )
        return response

    def _initialize(self):
        response = self._send(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "tiamat", "version": __version__},
            },
        )
        if response.status_code != 200:
            raise RuntimeError(f"OP.GG unavailable (HTTP {response.status_code})")
        self._session_id = response.headers.get("Mcp-Session-Id")
        self._send("notifications/initialized", notify=True)

    def _ensure_session(self, force=False):
        with self._lock:
            if force:
                self._session_id = None
            if self._session_id is None:
                self._initialize()

    def call_tool(self, name, arguments):
        self._ensure_session()
        params = {"name": name, "arguments": arguments}
        response = self._send("tools/call", params)
        if response.status_code in {400, 404}:
            # The server may forget idle sessions; start a new one once.
            self._ensure_session(force=True)
            response = self._send("tools/call", params)
        if response.status_code != 200:
            raise RuntimeError(f"OP.GG lookup failed (HTTP {response.status_code})")
        message = self._parse_body(response) or {}
        result = message.get("result") or {}
        if message.get("error") or result.get("isError"):
            return None
        return result

    def fetch_records(self, riot_id, region):
        """Return ``{queue_key: (wins, losses)}`` for a Riot ID, or None."""
        game_name, separator, tag_line = riot_id.rpartition("#")
        if not separator or not game_name or not tag_line or not region:
            return None
        result = self.call_tool(
            "lol_get_summoner_profile",
            {
                "game_name": game_name,
                "tag_line": tag_line,
                "region": region.upper(),
                "desired_output_fields": PROFILE_FIELDS,
                "client_app": CLIENT_APP,
            },
        )
        for item in (result or {}).get("content") or []:
            text = item.get("text", "") if isinstance(item, dict) else ""
            if text.startswith("class "):
                return records_from_profile(parse_compact(text))
        return None
