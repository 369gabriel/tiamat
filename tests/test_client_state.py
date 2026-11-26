import json

from ClientState import (
    DISCONNECTED,
    ClientSnapshot,
    ClientStateMonitor,
    HomeView,
    build_champ_select_view,
    build_home_view,
    RankEntry,
    TeamMember,
    resolve_team_players,
    resolve_team_riot_ids,
)
from Reveal import reveal
from widgets import render_live_text


class FakeResponse:
    def __init__(self, data=None, status_code=200):
        self.data = data
        self.status_code = status_code
        self.text = json.dumps(data)

    def json(self):
        return self.data


class FakeApi:
    def __init__(self, lcu=None, riot=None):
        self.lcu = lcu or {}
        self.riot = riot or {}
        self.calls = []

    def _respond(self, routes, endpoint):
        self.calls.append(endpoint)
        if endpoint not in routes:
            return FakeResponse({"errorCode": "RPC_ERROR"}, 404)
        value = routes[endpoint]
        return value if isinstance(value, FakeResponse) else FakeResponse(value)

    def lcu_request(self, _method, endpoint, _body):
        return self._respond(self.lcu, endpoint)

    def riot_request(self, _method, endpoint, _body):
        return self._respond(self.riot, endpoint)


GOLD_TWO = RankEntry("GOLD", "II", 45, 12, 10)
DIAMOND_ONE = RankEntry("DIAMOND", "I", 80, 30, 30)

CHAMPIONS = {103: "Ahri", 99: "Lux", 238: "Zed", 157: "Yasuo", 777: "Yone"}


def champ_select_session(hidden=False):
    visibility = "HIDDEN" if hidden else "VISIBLE"
    return {
        "gameId": 42,
        "localPlayerCellId": 2,
        "myTeam": [
            {"cellId": 0, "assignedPosition": "top", "championId": 103, "summonerId": 10,
             "puuid": "p0", "nameVisibilityType": visibility},
            {"cellId": 1, "assignedPosition": "jungle", "championId": 99, "summonerId": 11,
             "puuid": "p1", "nameVisibilityType": visibility},
            {"cellId": 2, "assignedPosition": "middle", "championId": 0, "championPickIntent": 238,
             "summonerId": 12, "puuid": "p2", "nameVisibilityType": visibility},
        ],
        "actions": [
            [
                {"id": 1, "actorCellId": 0, "type": "ban", "championId": 157, "completed": True},
                {"id": 2, "actorCellId": 6, "type": "ban", "championId": 777, "completed": True},
            ],
            [
                {"id": 3, "actorCellId": 0, "type": "pick", "championId": 103, "completed": True},
                {"id": 4, "actorCellId": 1, "type": "pick", "championId": 99,
                 "completed": False, "isInProgress": True},
            ],
        ],
        "bans": {"myTeamBans": [], "theirTeamBans": []},
        "timer": {"phase": "BAN_PICK", "adjustedTimeLeftInPhase": 23000,
                  "internalNowInEpochMs": 1_000_000},
    }


def test_visible_names_resolve_by_summoner_id():
    api = FakeApi(lcu={
        f"/lol-summoner/v1/summoners/{summoner_id}": {"gameName": f"Player {summoner_id}", "tagLine": "BR1"}
        for summoner_id in (10, 11, 12)
    })

    names, unmatched = resolve_team_riot_ids(api, champ_select_session())

    assert names == {0: "Player 10#BR1", 1: "Player 11#BR1", 2: "Player 12#BR1"}
    assert unmatched == []


def test_hidden_names_match_by_puuid_and_never_guess_the_rest():
    api = FakeApi(riot={"/chat/v5/participants": {"participants": [
        {"cid": "abc@champ-select.pvp.net", "puuid": "p2", "game_name": "Me", "game_tag": "BR1"},
        {"cid": "abc@champ-select.pvp.net", "puuid": "other", "game_name": "Mystery", "game_tag": "X"},
        {"cid": "lobby@sec.pvp.net", "puuid": "p0", "game_name": "Not Here", "game_tag": "Y"},
    ]}})

    session = champ_select_session(hidden=True)
    names, unmatched = resolve_team_riot_ids(api, session)
    players, unmatched_players = resolve_team_players(api, session)

    assert names == {2: "Me#BR1"}
    assert unmatched == ["Mystery#X"]
    assert players == {2: ("Me#BR1", "p2")}
    assert unmatched_players == [("Mystery#X", "other")]


def test_champ_select_view_reports_lock_hover_bans_and_deadline():
    view = build_champ_select_view(
        champ_select_session(),
        {0: ("Top#1", "p0"), 2: ("Me#BR1", "p2")},
        [("Mystery#X", "other")],
        CHAMPIONS,
        ranks={"p0": GOLD_TWO, "p1": None, "other": DIAMOND_ONE},
    )

    assert view.action == "pick"
    assert view.deadline_ms == 1_023_000
    top, jungle, mid = view.team
    assert (top.position, top.name, top.champion, top.state) == ("TOP", "Top#1", "Ahri", "locked")
    assert (jungle.position, jungle.name, jungle.champion, jungle.state) == ("JGL", None, "Lux", "hover")
    assert (mid.champion, mid.state, mid.is_local) == ("Zed", "hover", True)
    assert view.my_bans == ("Yasuo",)
    assert view.their_bans == ("Yone",)
    assert (top.rank, top.rank_loaded) == (GOLD_TWO, True)
    assert (jungle.rank, jungle.rank_loaded) == (None, True)  # unranked, ranked by team puuid
    assert mid.rank_loaded is False
    assert view.unmatched == (
        TeamMember(None, "", "Mystery#X", None, "", False, DIAMOND_ONE, True),
    )
    assert view.rank_queue == "SOLO/DUO"


def test_champ_select_render_shows_team_and_countdown():
    view = build_champ_select_view(
        champ_select_session(),
        {0: ("Top#1", "p0"), 2: ("Me#BR1", "p2")},
        [("Mystery#X", "other")],
        CHAMPIONS,
        ranks={"p0": GOLD_TWO, "p1": None, "other": DIAMOND_ONE},
    )
    text = render_live_text(
        ClientSnapshot(True, "ChampSelect", champ_select=view), now_ms=1_000_000
    )

    assert "CHAMP SELECT" in text
    assert "pick  0:23" in text
    assert "PLAYER" in text and "SOLO/DUO" in text and "WR" in text
    assert "G2 45LP" in text and "55% 22g" in text
    assert "unranked" in text
    assert "> MID  Me#BR1" in text and "…" in text
    assert "IN LOBBY" in text and "Mystery#X" in text and "D1 80LP" in text
    assert "Multi-Search" not in text
    assert "hidden" in text
    assert "Ahri" in text and "Lux" in text
    assert "Yasuo" in text and "Yone" in text


def test_home_view_ranked_and_unranked():
    home = build_home_view(
        {"gameName": "pure hearted", "tagLine": "gift", "summonerLevel": 312,
         "percentCompleteForNextLevel": 45},
        {"queueMap": {
            "RANKED_SOLO_5x5": {"tier": "GOLD", "division": "II", "leaguePoints": 45,
                                "wins": 12, "losses": 10},
            "RANKED_FLEX_SR": {"tier": "", "division": "NA"},
        }},
        "chat",
    )
    text = render_live_text(
        ClientSnapshot(True, "None", home=home),
        automations=(("Instalock", "Ahri  (fallback Lux)"), ("AutoBan", "OFF")),
    )

    assert home.solo.tier == "GOLD" and home.flex is None
    assert "HOME" in text
    assert "pure hearted#gift" in text
    assert "Level 312  (45% to next)" in text
    assert "chat online" in text
    assert "Gold II  45 LP" in text
    assert "12W 10L  55%" in text
    assert "Unranked" in text
    assert "fallback Lux" in text


def test_disconnected_render():
    assert "WAITING FOR LEAGUE CLIENT" in render_live_text(DISCONNECTED)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_monitor_publishes_only_changes_and_caches_home_data():
    api = FakeApi(lcu={
        "/lol-gameflow/v1/gameflow-phase": "None",
        "/lol-summoner/v1/current-summoner": {"gameName": "A", "tagLine": "B", "summonerLevel": 5},
        "/lol-ranked/v1/current-ranked-stats": {"queueMap": {}},
        "/lol-chat/v1/me": {"availability": "chat"},
    })
    sent = []
    clock = Clock()
    monitor = ClientStateMonitor(sent.append, rengar=api, clock=clock)

    assert monitor.publish(monitor.poll())
    clock.now = 1
    assert not monitor.publish(monitor.poll())
    assert api.calls.count("/lol-summoner/v1/current-summoner") == 1

    api.lcu["/lol-gameflow/v1/gameflow-phase"] = "Lobby"
    clock.now = 2
    assert monitor.publish(monitor.poll())
    assert api.calls.count("/lol-summoner/v1/current-summoner") == 2
    assert [snapshot.phase for snapshot in sent] == ["None", "Lobby"]
    assert sent[-1].home == HomeView(riot_id="A#B", level=5, chat_status="online")


def test_monitor_champ_select_caches_names_until_unresolved_retry():
    session = champ_select_session()
    lcu = {
        "/lol-gameflow/v1/gameflow-phase": "ChampSelect",
        "/lol-champ-select/v1/session": session,
        "/lol-game-data/assets/v1/champion-summary.json": [
            {"id": champion_id, "name": name} for champion_id, name in CHAMPIONS.items()
        ],
        "/lol-summoner/v1/summoners/10": {"gameName": "Top", "tagLine": "1"},
        "/lol-summoner/v1/summoners/11": {"gameName": "Jungle", "tagLine": "2"},
        "/lol-summoner/v1/summoners/12": {"gameName": "Me", "tagLine": "BR1"},
        "/lol-gameflow/v1/session": {"gameData": {"queue": {"id": 440, "type": "RANKED_FLEX_SR"}}},
        "/lol-ranked/v1/ranked-stats/p0": {"queueMap": {
            "RANKED_SOLO_5x5": {"tier": "IRON", "division": "IV"},
            "RANKED_FLEX_SR": {"tier": "GOLD", "division": "II", "leaguePoints": 45,
                               "wins": 12, "losses": 10},
        }},
        "/lol-ranked/v1/ranked-stats/p1": {"queueMap": {}},
        # p2 fails: it is retried a bounded number of times, then left unknown.
    }
    api = FakeApi(lcu=lcu)
    clock = Clock()
    monitor = ClientStateMonitor(rengar=api, clock=clock)

    snapshot = monitor.poll()
    for second in range(1, 6):
        clock.now = second
        monitor.poll()

    view = snapshot.champ_select
    assert [member.name for member in view.team] == ["Top#1", "Jungle#2", "Me#BR1"]
    assert view.rank_queue == "FLEX"
    assert view.team[0].rank == GOLD_TWO
    assert (view.team[1].rank, view.team[1].rank_loaded) == (None, True)
    assert view.team[2].rank_loaded is False
    assert api.calls.count("/lol-ranked/v1/ranked-stats/p0") == 1
    assert api.calls.count("/lol-ranked/v1/ranked-stats/p2") == 3
    assert api.calls.count("/lol-gameflow/v1/session") == 1
    assert snapshot.home is None
    assert api.calls.count("/lol-summoner/v1/summoners/10") == 1
    assert api.calls.count("/lol-game-data/assets/v1/champion-summary.json") == 1


def test_reveal_uses_shared_name_resolution():
    api = FakeApi(
        lcu={
            "/lol-champ-select/v1/session": champ_select_session(hidden=True),
            "/riotclient/region-locale": {"webRegion": "br"},
        },
        riot={"/chat/v5/participants": {"participants": [
            {"cid": "x@champ-select", "puuid": "p2", "game_name": "Me", "game_tag": "BR1"},
            {"cid": "x@champ-select", "puuid": "", "game_name": "Friend", "game_tag": "TAG"},
        ]}},
    )

    url = reveal(provider="opgg", rengar=api, open_browser=False)

    assert url == "https://www.op.gg/multisearch/br?summoners=Me%23BR1,Friend%23TAG"


def test_hidden_losses_show_wins_instead_of_a_fake_winrate():
    # The LCU reports 0 losses for other players; 23-0 must not render as 100%.
    hidden = {"tier": "EMERALD", "division": "II", "leaguePoints": 55, "wins": 23, "losses": 0}
    view = build_champ_select_view(
        champ_select_session(),
        {0: ("Smoochie Girl#Gwen", "p0")},
        [],
        CHAMPIONS,
        ranks={"p0": build_home_view({}, {"queueMap": {"RANKED_SOLO_5x5": hidden}}, None).solo},
    )
    rank = view.team[0].rank

    assert (rank.losses, rank.games, rank.winrate) == (None, None, None)
    text = render_live_text(ClientSnapshot(True, "ChampSelect", champ_select=view), now_ms=0)
    assert "E2 55LP" in text and "23W" in text
    assert "100%" not in text

    home = render_live_text(ClientSnapshot(True, "None", home=HomeView(solo=rank)))
    assert "Emerald II  55 LP   23W" in home and "%" not in home

