"""FastAPI web server that wraps Tiamat's functionality into a REST API."""

import threading
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

# ── Tiamat modules ──────────────────────────────────────────────────────────
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from AutoAccept import AutoAccept
from Backgrounds import (
    change_profile_background,
    fetch_all_champion_skins,
    fetch_skin_background,
    get_skin_assets,
    search_skins_by_name,
)
from Badges import change_profile_badges
from Config import load_config, save_config
from disconnect_reconnect_chat import Chat
from Dodge import dodge
from Icons import change_profile_icon
from Iconsclient import icon_client
from InstalockAutoban import InstalockAutoban
from RageQueue import RageQueue
from RemoveFriends import get_friends, remove_all_friends
from Rengar import Rengar, find_league_client_credentials
from RestartUX import restart
from Reveal import reveal
from Riotidchanger import change_riotid
from StatusChanger import change_status

# ── FastAPI app ─────────────────────────────────────────────────────────────

app = FastAPI(title="Tiamat Web", version="0.1.0")

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"

app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


# ── Global state ────────────────────────────────────────────────────────────

config = load_config()
connected = False
account_name = "League Client not detected"
rengar_instance = None
chat_instance = None

auto_accept = AutoAccept(config, on_event=lambda l, m: add_activity(l, m))
champion_automation = InstalockAutoban(config, on_event=lambda l, m: add_activity(l, m))
ragequeue = RageQueue(config, on_event=lambda l, m: add_activity(l, m))

activity_log: list[dict] = []
activity_lock = threading.Lock()
_monitors_started = False

REGALIA_ASSET_BASE = "https://raw.communitydragon.org/latest"
PRESTIGE_CREST_LEVELS = [
    1, 30, 50, 75, 100, 125, 150, 175, 200, 225,
    250, 275, 300, 325, 350, 375, 400, 425, 450, 475, 500,
]


# ── Helpers ─────────────────────────────────────────────────────────────────

def add_activity(level: str, message: str):
    timestamp = datetime.now().strftime("%H:%M")
    entry = {"timestamp": timestamp, "level": level, "message": str(message)}
    with activity_lock:
        activity_log.append(entry)
        if len(activity_log) > 200:
            activity_log[:] = activity_log[-200:]
    # broadcast via websocket if needed
    return entry


def build_regalia_assets(regalia: dict) -> dict:
    crest_url = ""
    crest_type = regalia.get("crestType", "")
    if crest_type == "prestige":
        selected = int(regalia.get("selectedPrestigeCrest", 0) or 0)
        if 1 <= selected <= len(PRESTIGE_CREST_LEVELS):
            crest_level = PRESTIGE_CREST_LEVELS[selected - 1]
        else:
            summoner_level = int(regalia.get("summonerLevel", 1) or 1)
            summoner_level = max(1, summoner_level)
            crest_level = max(
                level for level in PRESTIGE_CREST_LEVELS
                if level <= min(summoner_level, PRESTIGE_CREST_LEVELS[-1])
            )
        crest_url = (
            f"{REGALIA_ASSET_BASE}/game/assets/loadouts/regalia/crests/"
            f"prestige/prestige_crest_lvl_{crest_level:03}.png"
        )

    banner_type = regalia.get("bannerType", "")
    if banner_type == "lastSeasonHighestRank":
        banner_tier = regalia.get("lastSeasonHighestRank", "")
    elif banner_type == "highestRankedEntry":
        banner_tier = regalia.get("highestRankedEntry", {}).get("tier", "")
    else:
        banner_tier = ""
    banner_tier = (banner_tier or "default").lower()
    banner_base = (
        f"{REGALIA_ASSET_BASE}/plugins/rcp-be-lol-game-data/global/default/"
        "assets/regalia"
    )
    return {
        "crestUrl": crest_url,
        "bannerUrl": f"{banner_base}/bannerskins/{banner_tier}.png",
    }


def read_account_text(api: Rengar) -> str:
    summoner_resp = api.lcu_request("GET", "/lol-summoner/v1/current-summoner", "")
    region_resp = api.lcu_request("GET", "/riotclient/region-locale", "")
    if summoner_resp.status_code != 200:
        return "League Client connected"
    s = summoner_resp.json()
    riot_id = f"{s.get('gameName', 'Unknown')}#{s.get('tagLine', 'Unknown')}"
    region = ""
    if region_resp.status_code == 200:
        region = region_resp.json().get("webRegion", "").upper()
    return f"connected  {riot_id}" + (f"  {region}" if region else "")


def ensure_connected():
    global connected, account_name, rengar_instance, chat_instance, _monitors_started
    port, token = find_league_client_credentials()
    if port and token:
        if not connected:
            api = Rengar()
            try:
                name = read_account_text(api)
                chat = Chat(api)
                connected = True
                account_name = name
                rengar_instance = api
                chat_instance = chat
                auto_accept.rengar = api
                champion_automation.rengar = api
                ragequeue.rengar = api
                add_activity("system", "Connected to League Client")
                if not _monitors_started:
                    _monitors_started = True
                    _start_monitors()
            except Exception as e:
                add_activity("error", f"Connection error: {e}")
        return True
    else:
        if connected:
            connected = False
            account_name = "League Client not detected"
            chat_instance = None
            add_activity("warning", "League Client disconnected")
        return False


def _start_monitors():
    def run_aa():
        auto_accept.monitor_queue()
    threading.Thread(target=run_aa, daemon=True).start()

    def run_cs():
        champion_automation.monitor_champ_select()
    threading.Thread(target=run_cs, daemon=True).start()

    def run_rq():
        ragequeue.monitor_gameflow()
    threading.Thread(target=run_rq, daemon=True).start()


# ── WebSocket manager ───────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self._connections:
            self._connections.remove(ws)

    async def broadcast(self, data: dict):
        for ws in self._connections[:]:
            try:
                await ws.send_json(data)
            except Exception:
                pass


manager = ConnectionManager()


# ── Connection monitor thread ───────────────────────────────────────────────

def connection_monitor():
    prev_connected = False
    while True:
        now_connected = ensure_connected()
        if now_connected != prev_connected:
            import asyncio
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    manager.broadcast({
                        "type": "connection",
                        "connected": connected,
                        "account": account_name,
                    })
                )
                loop.close()
            except Exception:
                pass
            prev_connected = now_connected
        time.sleep(2)


_thread = threading.Thread(target=connection_monitor, daemon=True)
_thread.start()


# ── Feature state helpers ───────────────────────────────────────────────────

def feature_state(number: int) -> str:
    if number == 1:
        return "ON" if auto_accept.auto_accept_enabled else "OFF"
    if number == 2:
        return champion_automation.instalock_champion if champion_automation.instalock_enabled else "OFF"
    if number == 3:
        return champion_automation.auto_ban_champion if champion_automation.auto_ban_enabled else "OFF"
    if number == 4:
        return ragequeue.queue_name if ragequeue.enabled else "OFF"
    if number == 14:
        return chat_instance.return_state() if chat_instance else "--"
    return ""


def require_connection():
    if not ensure_connected():
        add_activity("warning", "Start the League Client before using this module")
        return False
    return True


# ── REST endpoints ──────────────────────────────────────────────────────────

@app.get("/api/status")
def get_status():
    ensure_connected()
    features = []
    for f in [
        {"number": 1, "title": "Auto Accept", "kind": "toggle"},
        {"number": 2, "title": "Instalock", "kind": "configure"},
        {"number": 3, "title": "AutoBan", "kind": "configure"},
        {"number": 4, "title": "Ragequeue", "kind": "configure"},
        {"number": 14, "title": "Disconnect Chat", "kind": "toggle"},
    ]:
        features.append({**f, "state": feature_state(f["number"])})

    return {
        "connected": connected,
        "account": account_name,
        "features": features,
        "activity": list(reversed(activity_log[-50:])),
    }


@app.get("/api/features")
def get_features():
    return [
        {"number": 1, "category": "AUTOMATION", "title": "Auto Accept", "description": "Automatically accepts ready checks when a match is found.", "kind": "toggle"},
        {"number": 2, "category": "AUTOMATION", "title": "Instalock", "description": "Selects and locks your preferred champion during champion select.", "kind": "configure"},
        {"number": 3, "category": "AUTOMATION", "title": "AutoBan", "description": "Automatically bans your preferred champion during champion select.", "kind": "configure"},
        {"number": 4, "category": "AUTOMATION", "title": "Ragequeue", "description": "Creates your preferred lobby and resumes matchmaking after games.", "kind": "configure"},
        {"number": 5, "category": "CUSTOMIZATION", "title": "Profile Icon", "description": "Changes the profile icon visible on your Riot account.", "kind": "configure"},
        {"number": 6, "category": "CUSTOMIZATION", "title": "Client-Only Icon", "description": "Changes the icon shown only inside the local League Client.", "kind": "configure"},
        {"number": 7, "category": "CUSTOMIZATION", "title": "Profile Background", "description": "Searches champion skins and applies one as your profile background.", "kind": "configure"},
        {"number": 8, "category": "CUSTOMIZATION", "title": "Riot ID", "description": "Changes the game name and tag displayed on your Riot account.", "kind": "configure"},
        {"number": 9, "category": "CUSTOMIZATION", "title": "Profile Badges", "description": "Clears, duplicates, or applies glitched profile badges.", "kind": "configure"},
        {"number": 10, "category": "CUSTOMIZATION", "title": "Status Message", "description": "Updates the multiline status displayed to your friends.", "kind": "configure"},
        {"number": 11, "category": "GAME TOOLS", "title": "Lobby Reveal", "description": "Opens the current champion-select lobby on Porofessor.", "kind": "action"},
        {"number": 12, "category": "GAME TOOLS", "title": "Dodge", "description": "Leaves the current champion select without restarting the client.", "kind": "action", "destructive": True},
        {"number": 13, "category": "GAME TOOLS", "title": "Restart Client UX", "description": "Restarts the League Client interface without closing the game.", "kind": "action", "destructive": True},
        {"number": 15, "category": "SOCIAL", "title": "Remove All Friends", "description": "Permanently removes every friend from the account.", "kind": "action", "destructive": True},
    ]


# ── Toggle features ─────────────────────────────────────────────────────────

@app.post("/api/toggle/auto-accept")
def toggle_auto_accept():
    if not require_connection():
        return {"error": "Not connected"}
    state = auto_accept.toggle_auto_accept()
    return {"state": feature_state(1)}


@app.post("/api/toggle/chat")
def toggle_chat():
    if not require_connection() or not chat_instance:
        return {"error": "Not connected"}
    chat_instance.toggle_chat()
    return {"state": feature_state(14)}


# ── Automation toggles ──────────────────────────────────────────────────────

@app.post("/api/toggle/instalock")
def toggle_instalock():
    if not require_connection():
        return {"error": "Not connected"}
    champion_automation.toggle_instalock()
    return {"state": feature_state(2)}


@app.post("/api/toggle/autoban")
def toggle_autoban():
    if not require_connection():
        return {"error": "Not connected"}
    champion_automation.toggle_auto_ban()
    return {"state": feature_state(3)}


@app.post("/api/toggle/ragequeue")
def toggle_ragequeue():
    if not require_connection():
        return {"error": "Not connected"}
    if ragequeue.enabled:
        ragequeue.disable()
    else:
        return {"error": "Configure ragequeue first", "need_config": True}
    return {"state": feature_state(4)}


# ── Champion selection ──────────────────────────────────────────────────────

@app.get("/api/champions")
def list_champions():
    if not require_connection():
        return {"error": "Not connected"}
    try:
        names = champion_automation.update_champion_list()
        return {"champions": names}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/configure/instalock")
def set_instalock(data: dict):
    if not require_connection():
        return {"error": "Not connected"}
    try:
        champion_automation.set_instalock_champion(data["champion"])
        return {"state": feature_state(2)}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/configure/autoban")
def set_autoban(data: dict):
    if not require_connection():
        return {"error": "Not connected"}
    try:
        champion_automation.set_auto_ban_champion(data["champion"])
        return {"state": feature_state(3)}
    except Exception as e:
        return {"error": str(e)}


# ── Ragequeue ───────────────────────────────────────────────────────────────

@app.get("/api/ragequeue/queues")
def get_queues():
    return {
        "queues": [
            {"id": qid, "name": name}
            for qid, (name, _) in RageQueue.QUEUE_TYPES.items()
        ],
        "positions": [
            {"id": pid, "name": name}
            for pid, (name, _) in RageQueue.POSITION_TYPES.items()
        ],
    }


@app.post("/api/configure/ragequeue")
def set_ragequeue(data: dict):
    if not require_connection():
        return {"error": "Not connected"}
    try:
        ragequeue.configure(
            data["queue_id"],
            data.get("first_position"),
            data.get("second_position"),
        )
        return {"state": feature_state(4)}
    except Exception as e:
        return {"error": str(e)}


# ── Profile Icon ────────────────────────────────────────────────────────────

@app.post("/api/configure/profile-icon")
def set_profile_icon(data: dict):
    if not require_connection():
        return {"error": "Not connected"}
    try:
        change_profile_icon(data["icon_id"], rengar_instance)
        add_activity("success", f"Profile icon changed to {data['icon_id']}")
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/configure/client-icon")
def set_client_icon(data: dict):
    if not require_connection():
        return {"error": "Not connected"}
    try:
        icon_client(data["icon_id"], rengar_instance)
        add_activity("success", f"Client icon changed to {data['icon_id']}")
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


# ── Profile Background ──────────────────────────────────────────────────────

@app.get("/api/skins")
def list_skins(query: str = "", collection: str = "all", sort: str = "name"):
    try:
        all_skins = fetch_all_champion_skins()

        inventory = {}
        if connected and rengar_instance:
            inventory_resp = rengar_instance.lcu_request(
                "GET", "/lol-inventory/v2/inventory/CHAMPION_SKIN", ""
            )
            if inventory_resp.status_code == 200:
                inventory = {
                    str(item.get("itemId")): item
                    for item in inventory_resp.json() or []
                    if item.get("owned")
                }

        for skin in all_skins:
            owned_item = inventory.get(skin["id"])
            purchase_date = owned_item.get("purchaseDate", "") if owned_item else ""
            skin["owned"] = owned_item is not None
            skin["purchaseDate"] = purchase_date
            skin["acquiredYear"] = purchase_date[:4] if purchase_date else ""

        if query:
            all_skins = search_skins_by_name(all_skins, query)
        if collection == "owned":
            all_skins = [skin for skin in all_skins if skin["owned"]]

        if sort == "name":
            all_skins.sort(key=lambda skin: (skin["champion"], skin["name"]))
        elif sort == "oldest":
            all_skins.sort(key=lambda skin: skin["purchaseDate"] or "99999999")
        else:
            all_skins.sort(
                key=lambda skin: skin["purchaseDate"] or "00000000", reverse=True
            )

        return {"skins": all_skins, "total": len(all_skins)}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/configure/background")
def set_background(data: dict):
    if not require_connection():
        return {"error": "Not connected"}
    try:
        change_profile_background(data["skin_id"], rengar_instance)
        add_activity("success", f"Background changed to skin {data['skin_id']}")
        result = {
            "success": True,
            "skin_id": data["skin_id"],
            "backgroundUrl": "",
        }
        try:
            assets = get_skin_assets(data["skin_id"])
            result["tileUrl"] = assets["tileUrl"]
            if assets["backgroundUrl"]:
                result["backgroundUrl"] = (
                    f"/api/profile/background/{data['skin_id']}"
                )
        except Exception:
            result["tileUrl"] = ""
        return result
    except Exception as e:
        return {"error": str(e)}


# ── Riot ID ─────────────────────────────────────────────────────────────────

@app.post("/api/configure/riotid")
def set_riotid(data: dict):
    if not require_connection():
        return {"error": "Not connected"}
    try:
        result = change_riotid(data["name"], data["tag"], rengar_instance)
        add_activity("success", f"Riot ID changed to {result}")
        return {"success": True, "riotid": result}
    except Exception as e:
        return {"error": str(e)}


# ── Status Message ──────────────────────────────────────────────────────────

@app.post("/api/configure/status")
def set_status(data: dict):
    if not require_connection():
        return {"error": "Not connected"}
    try:
        change_status(data["status"], rengar_instance)
        add_activity("success", "Status message updated")
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


# ── Badges ──────────────────────────────────────────────────────────────────

@app.post("/api/configure/badges")
def set_badges(data: dict):
    if not require_connection():
        return {"error": "Not connected"}
    try:
        mode = data.get("mode", "empty")
        glitched_id = data.get("glitched_id")
        change_profile_badges(mode, glitched_id, rengar_instance)
        add_activity("success", f"Badges set to {mode}")
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


# ── Actions ─────────────────────────────────────────────────────────────────

@app.post("/api/action/lobby-reveal")
def action_reveal():
    if not require_connection():
        return {"error": "Not connected"}
    try:
        reveal(rengar_instance, open_browser=True)
        add_activity("success", "Lobby revealed on Porofessor")
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/action/dodge")
def action_dodge():
    if not require_connection():
        return {"error": "Not connected"}
    try:
        dodge(rengar_instance)
        add_activity("success", "Dodged champion select")
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/action/restart-ux")
def action_restart():
    if not require_connection():
        return {"error": "Not connected"}
    try:
        restart(rengar_instance)
        add_activity("success", "Client UX restarted")
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/action/remove-friends")
def action_remove_friends():
    if not require_connection():
        return {"error": "Not connected"}
    try:
        removed, failed = remove_all_friends(rengar=rengar_instance)
        add_activity("success", f"Removed {removed} friends ({failed} failed)")
        return {"success": True, "removed": removed, "failed": failed}
    except Exception as e:
        return {"error": str(e)}


# ── WebSocket for real-time updates ─────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            data = await ws.receive_json()
            # Client can send ping to keep alive
            if data.get("type") == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)


# ── Profile endpoint ────────────────────────────────────────────────────────

@app.get("/api/profile")
def get_profile():
    if not connected or not rengar_instance:
        ensure_connected()
    if not connected or not rengar_instance:
        return {"error": "Not connected"}

    try:
        api = rengar_instance
        # Current summoner
        sresp = api.lcu_request("GET", "/lol-summoner/v1/current-summoner", "")
        if sresp.status_code != 200:
            return {"error": "Could not fetch summoner data"}
        summoner = sresp.json()

        profile_data = {
            "gameName": summoner.get("gameName", "Unknown"),
            "tagLine": summoner.get("tagLine", "Unknown"),
            "profileIconId": summoner.get("profileIconId", 0),
            "summonerLevel": summoner.get("summonerLevel", 0),
            "xpSinceLastLevel": summoner.get("xpSinceLastLevel", 0),
            "xpUntilNextLevel": summoner.get("xpUntilNextLevel", 0),
            "summonerId": summoner.get("summonerId", 0),
        }

        # Current profile background preference and its splash-art asset.
        profile_resp = api.lcu_request(
            "GET", "/lol-summoner/v1/current-summoner/summoner-profile", ""
        )
        background_skin_id = 0
        if profile_resp.status_code == 200:
            background_skin_id = profile_resp.json().get("backgroundSkinId", 0)
        profile_data["backgroundSkinId"] = background_skin_id
        try:
            profile_data.update(get_skin_assets(background_skin_id))
            if profile_data["backgroundUrl"]:
                profile_data["backgroundUrl"] = (
                    f"/api/profile/background/{background_skin_id}"
                )
        except Exception:
            profile_data.update({"backgroundUrl": "", "tileUrl": ""})

        # Ranked data. The current-ranked-stats endpoint includes SR and TFT;
        # the older league positions endpoint is kept as a fallback.
        ranked = []
        rresp = api.lcu_request("GET", "/lol-ranked/v1/current-ranked-stats", "")
        if rresp.status_code == 200:
            queue_map = rresp.json().get("queueMap", {})
            queue_labels = {
                "RANKED_SOLO_5x5": "Ranked Solo/Duo",
                "RANKED_FLEX_SR": "Ranked Flex",
                "RANKED_TFT": "TFT",
            }
            for queue, label in queue_labels.items():
                entry = queue_map.get(queue)
                if entry:
                    ranked.append({
                        "queue": label,
                        "tier": entry.get("tier", "UNRANKED"),
                        "rank": entry.get("division", ""),
                        "leaguePoints": entry.get("leaguePoints", 0),
                        "wins": entry.get("wins", 0),
                        "losses": entry.get("losses", 0),
                        "miniSeries": entry.get("miniSeriesProgress"),
                    })

        if not ranked:
            legacy_resp = api.lcu_request(
                "GET",
                f"/lol-league/v2/positions/by-summoner/{summoner.get('summonerId', '')}",
                "",
            )
            if legacy_resp.status_code == 200:
                for entry in legacy_resp.json() or []:
                    queue = entry.get("queueType", "")
                    if queue in {"RANKED_SOLO_5x5", "RANKED_FLEX_SR"}:
                        label = "Ranked Solo/Duo" if queue == "RANKED_SOLO_5x5" else "Ranked Flex"
                        ranked.append({
                            "queue": label,
                            "tier": entry.get("tier", "UNRANKED"),
                            "rank": entry.get("rank", ""),
                            "leaguePoints": entry.get("leaguePoints", 0),
                            "wins": entry.get("wins", 0),
                            "losses": entry.get("losses", 0),
                            "miniSeries": entry.get("miniSeries"),
                        })

        profile_data["ranked"] = ranked

        regalia_resp = api.lcu_request(
            "GET", "/lol-regalia/v2/current-summoner/regalia", ""
        )
        if regalia_resp.status_code == 200:
            profile_data["regalia"] = build_regalia_assets(regalia_resp.json())
        else:
            profile_data["regalia"] = {}

        # Supporting profile stats shown alongside ranks.
        profile_stats = {"honorLevel": 0, "masteryScore": 0, "title": ""}
        honor_resp = api.lcu_request("GET", "/lol-honor-v2/v1/profile", "")
        if honor_resp.status_code == 200:
            profile_stats["honorLevel"] = honor_resp.json().get("honorLevel", 0)
        mastery_resp = api.lcu_request(
            "GET", "/lol-champion-mastery/v1/local-player/champion-mastery-score", ""
        )
        if mastery_resp.status_code == 200:
            profile_stats["masteryScore"] = mastery_resp.json()
        challenges_resp = api.lcu_request(
            "GET", "/lol-challenges/v1/summary-player-data/local-player", ""
        )
        if challenges_resp.status_code == 200:
            profile_stats["title"] = (
                challenges_resp.json().get("title", {}).get("name", "")
            )
        profile_data["profileStats"] = profile_stats

        # Region
        regresp = api.lcu_request("GET", "/riotclient/region-locale", "")
        if regresp.status_code == 200:
            profile_data["region"] = regresp.json().get("webRegion", "").upper()
        else:
            profile_data["region"] = ""

        return profile_data

    except Exception as e:
        return {"error": str(e)}


@app.get("/api/profile/background/{skin_id}")
def get_profile_background_image(skin_id: int):
    try:
        content, media_type = fetch_skin_background(skin_id)
        return Response(
            content=content,
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=86400, immutable"},
        )
    except Exception:
        return Response(status_code=404)


# ── Serve SPA ───────────────────────────────────────────────────────────────
# Keep this catch-all after every API route so it cannot shadow an endpoint.

@app.get("/{path:path}")
async def serve_spa():
    index_path = STATIC / "index.html"
    if index_path.exists():
        return HTMLResponse(
            index_path.read_text(encoding="utf-8"),
            headers={"Cache-Control": "no-store"},
        )
    return HTMLResponse("<h1>Tiamat Web</h1><p>Frontend not found</p>")
