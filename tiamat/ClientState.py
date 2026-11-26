"""Read-only view of the League Client state for the live panel.

Everything here runs on a worker thread and produces plain, immutable
snapshots; the UI thread only renders them.
"""

import time
from dataclasses import dataclass

POSITION_LABELS = {
    "TOP": "TOP",
    "JUNGLE": "JGL",
    "MIDDLE": "MID",
    "BOTTOM": "BOT",
    "UTILITY": "SUP",
}

PHASE_LABELS = {
    "None": "HOME",
    "Lobby": "IN LOBBY",
    "Matchmaking": "IN QUEUE",
    "CheckedIntoTournament": "TOURNAMENT",
    "ReadyCheck": "MATCH FOUND",
    "ChampSelect": "CHAMP SELECT",
    "GameStart": "LOADING GAME",
    "FailedToLaunch": "FAILED TO LAUNCH",
    "InProgress": "IN GAME",
    "Reconnect": "RECONNECT",
    "WaitingForStats": "WAITING FOR STATS",
    "PreEndOfGame": "END OF GAME",
    "EndOfGame": "END OF GAME",
    "TerminatedInError": "GAME ERROR",
}

CHAT_STATUS_LABELS = {
    "chat": "online",
    "away": "away",
    "dnd": "in game",
    "mobile": "mobile",
    "offline": "offline",
}

HOME_REFRESH_SECONDS = 30
CHAT_REFRESH_SECONDS = 5
NAME_RETRY_SECONDS = 2
RANK_ATTEMPTS = 3


@dataclass(frozen=True)
class TeamMember:
    cell_id: int | None
    position: str
    name: str | None
    champion: str | None
    state: str  # "locked", "hover" or ""
    is_local: bool
    rank: "RankEntry | None" = None  # None means unranked once rank_loaded
    rank_loaded: bool = False


@dataclass(frozen=True)
class ChampSelectView:
    action: str  # "declare", "ban", "pick", "finalize" or ""
    deadline_ms: int | None  # epoch milliseconds when the current phase ends
    team: tuple
    my_bans: tuple
    their_bans: tuple
    unmatched: tuple = ()  # TeamMembers whose slot in the team is unknown
    rank_queue: str = "SOLO/DUO"


@dataclass(frozen=True)
class RankEntry:
    tier: str
    division: str
    league_points: int
    wins: int
    losses: int

    @property
    def games(self):
        return self.wins + self.losses

    @property
    def winrate(self):
        return round(self.wins * 100 / self.games) if self.games else None


@dataclass(frozen=True)
class HomeView:
    riot_id: str | None = None
    level: int | None = None
    level_progress: int | None = None
    solo: RankEntry | None = None
    flex: RankEntry | None = None
    chat_status: str | None = None


@dataclass(frozen=True)
class ClientSnapshot:
    connected: bool
    phase: str | None = None
    home: HomeView | None = None
    champ_select: ChampSelectView | None = None

    @property
    def phase_label(self):
        if self.phase is None:
            return ""
        return PHASE_LABELS.get(self.phase, self.phase.upper())


DISCONNECTED = ClientSnapshot(connected=False)


def _ok(response):
    return response is not None and response.status_code == 200


def _riot_id(game_name, tag_line):
    if game_name and tag_line:
        return f"{game_name}#{tag_line}"
    return None


def champ_select_chat_names(api):
    """Return (puuid, riot_id) pairs for everyone in the champ-select chat room."""
    response = api.riot_request("GET", "/chat/v5/participants", "")
    if not _ok(response):
        return []
    participants = []
    for participant in (response.json() or {}).get("participants", []):
        if "champ-select" not in participant.get("cid", ""):
            continue
        riot_id = _riot_id(participant.get("game_name"), participant.get("game_tag"))
        if riot_id:
            participants.append((participant.get("puuid") or "", riot_id))
    return participants


def resolve_team_players(api, session):
    """Resolve Riot IDs and puuids for the local team.

    Returns ``(players_by_cell, unmatched)`` where each player is a
    ``(riot_id, puuid)`` pair. When ranked hides names, the champ-select chat
    room is used; chat players that cannot be tied to a specific cell by puuid
    are returned in ``unmatched`` rather than guessed.
    """
    team = session.get("myTeam", []) or []
    hidden = any(player.get("nameVisibilityType") == "HIDDEN" for player in team)
    players = {}

    for player in team:
        riot_id = _riot_id(player.get("gameName"), player.get("tagLine"))
        if riot_id:
            players[player.get("cellId")] = (riot_id, player.get("puuid") or "")

    if hidden:
        participants = champ_select_chat_names(api)
        by_puuid = {puuid: riot_id for puuid, riot_id in participants if puuid}
        for player in team:
            cell_id = player.get("cellId")
            puuid = player.get("puuid")
            if cell_id not in players and puuid and puuid in by_puuid:
                players[cell_id] = (by_puuid[puuid], puuid)
        known = {riot_id for riot_id, _puuid in players.values()}
        unmatched = [
            (riot_id, puuid) for puuid, riot_id in participants if riot_id not in known
        ]
        return players, unmatched

    for player in team:
        cell_id = player.get("cellId")
        summoner_id = player.get("summonerId")
        if cell_id in players or not summoner_id or str(summoner_id) == "0":
            continue
        response = api.lcu_request("GET", f"/lol-summoner/v1/summoners/{summoner_id}", "")
        if _ok(response):
            summoner = response.json() or {}
            riot_id = _riot_id(summoner.get("gameName"), summoner.get("tagLine"))
            if riot_id:
                puuid = summoner.get("puuid") or player.get("puuid") or ""
                players[cell_id] = (riot_id, puuid)
    return players, []


def resolve_team_riot_ids(api, session):
    """Names-only view of :func:`resolve_team_players`, used by Multi-Search."""
    players, unmatched = resolve_team_players(api, session)
    return (
        {cell_id: riot_id for cell_id, (riot_id, _puuid) in players.items()},
        [riot_id for riot_id, _puuid in unmatched],
    )


def _champion_name(champions, champion_id):
    if not champion_id or champion_id <= 0:
        return None
    return champions.get(champion_id, f"#{champion_id}")


def _current_action(session):
    timer = session.get("timer") or {}
    phase = timer.get("phase")
    if phase == "PLANNING":
        return "declare"
    if phase == "FINALIZATION":
        return "finalize"
    if phase == "BAN_PICK":
        for group in session.get("actions", []) or []:
            for action in group if isinstance(group, list) else []:
                if action.get("isInProgress") and not action.get("completed"):
                    action_type = action.get("type")
                    if action_type in {"ban", "pick"}:
                        return action_type
    return ""


def _deadline(session, now_ms):
    timer = session.get("timer") or {}
    left = timer.get("adjustedTimeLeftInPhase")
    if not isinstance(left, (int, float)) or timer.get("phase") in {None, "", "GAME_STARTING"}:
        return None
    base = timer.get("internalNowInEpochMs")
    if not isinstance(base, (int, float)) or base <= 0:
        base = now_ms
    return int(base + left)


def build_champ_select_view(
    session, players, unmatched, champions, ranks=None, rank_queue="SOLO/DUO", now_ms=None
):
    """``players`` maps cell id to ``(riot_id, puuid)``; ``unmatched`` is a list of
    such pairs; ``ranks`` maps puuid to a RankEntry (or None for unranked)."""
    now_ms = time.time() * 1000 if now_ms is None else now_ms
    ranks = ranks or {}

    def rank_fields(puuid):
        if puuid and puuid in ranks:
            return {"rank": ranks[puuid], "rank_loaded": True}
        return {}

    local_cell = session.get("localPlayerCellId")
    team = session.get("myTeam", []) or []
    team_cells = {player.get("cellId") for player in team}
    actions = [
        action
        for group in session.get("actions", []) or []
        if isinstance(group, list)
        for action in group
    ]
    locked_cells = {
        action.get("actorCellId")
        for action in actions
        if action.get("type") == "pick" and action.get("completed")
    }

    members = []
    for player in team:
        cell_id = player.get("cellId")
        champion_id = player.get("championId") or 0
        intent_id = player.get("championPickIntent") or 0
        if champion_id > 0 and cell_id in locked_cells:
            champion, state = _champion_name(champions, champion_id), "locked"
        elif champion_id > 0:
            champion, state = _champion_name(champions, champion_id), "hover"
        elif intent_id > 0:
            champion, state = _champion_name(champions, intent_id), "hover"
        else:
            champion, state = None, ""
        name, puuid = players.get(cell_id, (None, ""))
        members.append(
            TeamMember(
                cell_id=cell_id,
                position=POSITION_LABELS.get((player.get("assignedPosition") or "").upper(), ""),
                name=name,
                champion=champion,
                state=state,
                is_local=cell_id == local_cell,
                **rank_fields(puuid or player.get("puuid")),
            )
        )

    bans = session.get("bans") or {}
    my_ban_ids = [champion_id for champion_id in bans.get("myTeamBans", []) or [] if champion_id > 0]
    their_ban_ids = [champion_id for champion_id in bans.get("theirTeamBans", []) or [] if champion_id > 0]
    if not my_ban_ids and not their_ban_ids:
        for action in actions:
            if action.get("type") != "ban" or not action.get("completed"):
                continue
            champion_id = action.get("championId") or 0
            if champion_id <= 0:
                continue
            if action.get("actorCellId") in team_cells:
                my_ban_ids.append(champion_id)
            else:
                their_ban_ids.append(champion_id)

    return ChampSelectView(
        action=_current_action(session),
        deadline_ms=_deadline(session, now_ms),
        team=tuple(members),
        my_bans=tuple(_champion_name(champions, champion_id) for champion_id in my_ban_ids),
        their_bans=tuple(_champion_name(champions, champion_id) for champion_id in their_ban_ids),
        unmatched=tuple(
            TeamMember(None, "", riot_id, None, "", False, **rank_fields(puuid))
            for riot_id, puuid in unmatched
        ),
        rank_queue=rank_queue,
    )


def _rank_entry(queue):
    if not isinstance(queue, dict):
        return None
    tier = (queue.get("tier") or "").upper()
    if tier in {"", "NONE"}:
        return None
    division = queue.get("division") or ""
    if division in {"NA", "NONE"}:
        division = ""
    return RankEntry(
        tier=tier,
        division=division,
        league_points=int(queue.get("leaguePoints") or 0),
        wins=int(queue.get("wins") or 0),
        losses=int(queue.get("losses") or 0),
    )


def build_home_view(summoner, ranked, chat_status):
    summoner = summoner or {}
    queue_map = (ranked or {}).get("queueMap") or {}
    level = summoner.get("summonerLevel")
    progress = summoner.get("percentCompleteForNextLevel")
    return HomeView(
        riot_id=_riot_id(summoner.get("gameName"), summoner.get("tagLine")),
        level=level if isinstance(level, int) else None,
        level_progress=progress if isinstance(progress, int) else None,
        solo=_rank_entry(queue_map.get("RANKED_SOLO_5x5")),
        flex=_rank_entry(queue_map.get("RANKED_FLEX_SR")),
        chat_status=CHAT_STATUS_LABELS.get(chat_status, chat_status) if chat_status else None,
    )


class ClientStateMonitor:
    def __init__(self, on_snapshot=None, rengar=None, clock=time.monotonic):
        self.on_snapshot = on_snapshot or (lambda _snapshot: None)
        self.clock = clock
        self._running = True
        self.attach(rengar)

    def attach(self, rengar):
        """Point the monitor at a (new) client connection and forget cached state."""
        self.rengar = rengar
        self._champions = {}
        self._last_phase = None
        self._last_sent = None
        self._summoner = None
        self._ranked = None
        self._home_at = None
        self._chat_status = None
        self._chat_at = None
        self._reset_champ_select()

    def _reset_champ_select(self):
        self._names_key = None
        self._players = {}
        self._unmatched = []
        self._names_at = None
        self._ranks = {}
        self._rank_attempts = {}
        self._rank_queue = None

    def _get_json(self, endpoint):
        response = self.rengar.lcu_request("GET", endpoint, "")
        return response.json() if _ok(response) else None

    def _ensure_champions(self):
        if self._champions:
            return
        data = self._get_json("/lol-game-data/assets/v1/champion-summary.json")
        if isinstance(data, list):
            self._champions = {
                champion["id"]: champion["name"]
                for champion in data
                if isinstance(champion, dict) and champion.get("id", 0) > 0 and champion.get("name")
            }

    def _stale(self, stamp, seconds):
        return stamp is None or self.clock() - stamp >= seconds

    def _home(self, phase_changed):
        if phase_changed or self._stale(self._home_at, HOME_REFRESH_SECONDS):
            self._summoner = self._get_json("/lol-summoner/v1/current-summoner")
            self._ranked = self._get_json("/lol-ranked/v1/current-ranked-stats")
            self._home_at = self.clock()
        if phase_changed or self._stale(self._chat_at, CHAT_REFRESH_SECONDS):
            me = self._get_json("/lol-chat/v1/me")
            self._chat_status = (me or {}).get("availability")
            self._chat_at = self.clock()
        return build_home_view(self._summoner, self._ranked, self._chat_status)

    def _champ_select(self):
        response = self.rengar.lcu_request("GET", "/lol-champ-select/v1/session", "")
        if not _ok(response) or "RPC_ERROR" in (response.text or ""):
            return None
        session = response.json() or {}
        self._ensure_champions()

        key = session.get("gameId")
        if key != self._names_key:
            self._reset_champ_select()
        team = session.get("myTeam", []) or []
        unresolved = any(player.get("cellId") not in self._players for player in team)
        if self._names_at is None or (
            unresolved and self._stale(self._names_at, NAME_RETRY_SECONDS)
        ):
            try:
                self._players, self._unmatched = resolve_team_players(self.rengar, session)
            except Exception:
                # Names are best-effort; keep whatever was resolved before.
                pass
            self._names_key = key
            self._names_at = self.clock()

        if self._rank_queue is None:
            game = self._get_json("/lol-gameflow/v1/session") or {}
            queue_type = ((game.get("gameData") or {}).get("queue") or {}).get("type")
            self._rank_queue = "RANKED_FLEX_SR" if queue_type == "RANKED_FLEX_SR" else "RANKED_SOLO_5x5"

        puuids = [puuid for _riot_id, puuid in self._players.values()]
        puuids += [player.get("puuid") for player in team]
        puuids += [puuid for _riot_id, puuid in self._unmatched]
        for puuid in dict.fromkeys(puuid for puuid in puuids if puuid):
            self._load_rank(puuid)

        return build_champ_select_view(
            session,
            self._players,
            self._unmatched,
            self._champions,
            self._ranks,
            "FLEX" if self._rank_queue == "RANKED_FLEX_SR" else "SOLO/DUO",
        )

    def _load_rank(self, puuid):
        attempts = self._rank_attempts.get(puuid, 0)
        if puuid in self._ranks or attempts >= RANK_ATTEMPTS:
            return
        self._rank_attempts[puuid] = attempts + 1
        try:
            stats = self._get_json(f"/lol-ranked/v1/ranked-stats/{puuid}")
        except Exception:
            return
        if isinstance(stats, dict):
            queue_map = stats.get("queueMap") or {}
            self._ranks[puuid] = _rank_entry(queue_map.get(self._rank_queue))

    def poll(self):
        phase = self._get_json("/lol-gameflow/v1/gameflow-phase")
        if not isinstance(phase, str):
            phase = "None"
        phase_changed = phase != self._last_phase
        self._last_phase = phase
        if phase != "ChampSelect":
            self._reset_champ_select()

        champ_select = self._champ_select() if phase == "ChampSelect" else None
        home = None if champ_select else self._home(phase_changed)
        return ClientSnapshot(True, phase, home, champ_select)

    def publish(self, snapshot):
        if snapshot == self._last_sent:
            return False
        self._last_sent = snapshot
        self.on_snapshot(snapshot)
        return True

    def monitor(self):
        while self._running:
            if self.rengar is None:
                time.sleep(1)
                continue
            try:
                self.publish(self.poll())
                time.sleep(1)
            except Exception:
                # Display-only: never surface polling errors as notifications.
                time.sleep(2)

    def stop(self):
        self._running = False
