import json
from concurrent.futures import wait

import pytest

from ClientState import (
    ClientSnapshot,
    ClientStateMonitor,
    RankEntry,
    build_champ_select_view,
)
from OpggStats import CLIENT_APP, OpggClient, parse_compact, records_from_profile
from widgets import render_live_text

# Shape of a real lol_get_summoner_profile answer (trimmed).
SAMPLE = (
    "class LolGetSummonerProfile: data\n"
    "class Data: summoner\n"
    "class Summoner: game_name,tagline,league_stats\n"
    "class LeagueStat: game_type,tier_info,win,lose\n"
    "class TierInfo: tier,division,lp\n"
    "\n"
    'LolGetSummonerProfile(Data(Summoner("Smoochie Girl","Gwen",['
    'LeagueStat("SOLORANKED",TierInfo("EMERALD",2,55),23,14),'
    'LeagueStat("FLEXRANKED",TierInfo("EMERALD",1,75),10,4),'
    'LeagueStat("ARENA",TierInfo(null,null,null),null,null)])))'
)


def test_parse_compact_and_extract_records():
    profile = parse_compact(SAMPLE)

    assert profile["data"]["summoner"]["game_name"] == "Smoochie Girl"
    assert records_from_profile(profile) == {
        "RANKED_SOLO_5x5": (23, 14),
        "RANKED_FLEX_SR": (10, 4),
    }


@pytest.mark.parametrize(
    "expression",
    ['__import__("os").system("x")', "Data(open)", "Data(1).x", "Data(x=1)", "Data(1, 2)"],
)
def test_parse_compact_never_evaluates_code(expression):
    with pytest.raises((ValueError, SyntaxError)):
        parse_compact("class Data: summoner\n" + expression)


class FakeHttpResponse:
    def __init__(self, status_code=200, payload=None, headers=None, sse=False):
        self.status_code = status_code
        self.headers = dict(headers or {})
        if payload is None:
            self.text = ""
        elif sse:
            self.headers["Content-Type"] = "text/event-stream"
            self.text = f"event: message\ndata: {json.dumps(payload)}\n\n"
        else:
            self.headers["Content-Type"] = "application/json"
            self.text = json.dumps(payload)

    def json(self):
        return json.loads(self.text)


def tool_result(text):
    return {"jsonrpc": "2.0", "id": 2, "result": {"content": [
        {"type": "text", "text": text},
        {"type": "text", "text": "OP.GG page: https://www.op.gg/..."},
    ]}}


class FakePost:
    def __init__(self, tool_responses):
        self.tool_responses = list(tool_responses)
        self.calls = []
        self.sessions = 0

    def __call__(self, url, json, headers, timeout):
        self.calls.append((json, dict(headers)))
        method = json["method"]
        if method == "initialize":
            self.sessions += 1
            return FakeHttpResponse(200, {"jsonrpc": "2.0", "id": json["id"], "result": {}},
                                    headers={"Mcp-Session-Id": f"s{self.sessions}"})
        if method == "notifications/initialized":
            return FakeHttpResponse(202)
        return self.tool_responses.pop(0)


def test_client_fetches_records_over_mcp():
    post = FakePost([FakeHttpResponse(200, tool_result(SAMPLE), sse=True)])

    records = OpggClient(post=post).fetch_records("Smoochie Girl#Gwen", "br")

    assert records == {"RANKED_SOLO_5x5": (23, 14), "RANKED_FLEX_SR": (10, 4)}
    body, headers = post.calls[-1]
    assert body["method"] == "tools/call"
    assert headers["Mcp-Session-Id"] == "s1"
    arguments = body["params"]["arguments"]
    assert (arguments["game_name"], arguments["tag_line"], arguments["region"]) == (
        "Smoochie Girl", "Gwen", "BR"
    )
    assert arguments["client_app"] == CLIENT_APP


def test_client_restarts_an_expired_session_once():
    post = FakePost([FakeHttpResponse(404), FakeHttpResponse(200, tool_result(SAMPLE))])
    client = OpggClient(post=post)

    assert client.fetch_records("Smoochie Girl#Gwen", "BR")["RANKED_SOLO_5x5"] == (23, 14)
    assert post.sessions == 2


def test_client_returns_none_for_unknown_players_and_bad_ids():
    error = {"jsonrpc": "2.0", "id": 2, "result": {"isError": True, "content": [
        {"type": "text", "text": "Summoner not found"}]}}
    client = OpggClient(post=FakePost([FakeHttpResponse(200, error)]))

    assert client.fetch_records("Nobody#000", "BR") is None
    assert client.fetch_records("no tag", "BR") is None


SESSION = {
    "gameId": 7,
    "localPlayerCellId": 0,
    "myTeam": [{"cellId": 0, "assignedPosition": "middle", "championId": 0,
                "summonerId": 10, "puuid": "p0", "nameVisibilityType": "VISIBLE"}],
    "actions": [],
    "bans": {},
    "timer": {},
}
HIDDEN_LOSSES = RankEntry("EMERALD", "II", 55, 23, None)  # what the client gives


def test_opgg_record_fills_hidden_losses():
    view = build_champ_select_view(
        SESSION, {0: ("Smoochie Girl#Gwen", "p0")}, [], {},
        ranks={"p0": HIDDEN_LOSSES},
        records={"Smoochie Girl#Gwen": {"RANKED_SOLO_5x5": (23, 14)}},
    )
    rank = view.team[0].rank

    assert (rank.tier, rank.league_points, rank.wins, rank.losses, rank.winrate) == (
        "EMERALD", 55, 23, 14, 62
    )
    text = render_live_text(ClientSnapshot(True, "ChampSelect", champ_select=view), now_ms=0)
    assert "62% 37g" in text


def test_flex_games_use_the_flex_record_and_missing_records_keep_wins_only():
    records = {"Smoochie Girl#Gwen": {"RANKED_SOLO_5x5": (23, 14), "RANKED_FLEX_SR": (10, 4)}}
    flex = build_champ_select_view(
        SESSION, {0: ("Smoochie Girl#Gwen", "p0")}, [], {},
        ranks={"p0": HIDDEN_LOSSES}, rank_queue="FLEX", records=records,
    )
    missing = build_champ_select_view(
        SESSION, {0: ("Smoochie Girl#Gwen", "p0")}, [], {},
        ranks={"p0": HIDDEN_LOSSES}, records={"Smoochie Girl#Gwen": {}},
    )

    assert (flex.team[0].rank.wins, flex.team[0].rank.losses) == (10, 4)
    assert missing.team[0].rank == HIDDEN_LOSSES


class FakeLcuResponse:
    def __init__(self, data, status_code=200):
        self.data, self.status_code, self.text = data, status_code, json.dumps(data)

    def json(self):
        return self.data


class FakeLcu:
    ROUTES = {
        "/lol-gameflow/v1/gameflow-phase": "ChampSelect",
        "/lol-champ-select/v1/session": SESSION,
        "/lol-game-data/assets/v1/champion-summary.json": [],
        "/lol-summoner/v1/summoners/10": {"gameName": "Smoochie Girl", "tagLine": "Gwen"},
        "/lol-gameflow/v1/session": {"gameData": {"queue": {"type": "RANKED_SOLO_5x5"}}},
        "/lol-ranked/v1/ranked-stats/p0": {"queueMap": {"RANKED_SOLO_5x5": {
            "tier": "EMERALD", "division": "II", "leaguePoints": 55, "wins": 23, "losses": 0}}},
        "/riotclient/region-locale": {"webRegion": "br"},
    }

    def lcu_request(self, _method, endpoint, _body):
        if endpoint in self.ROUTES:
            return FakeLcuResponse(self.ROUTES[endpoint])
        return FakeLcuResponse({"errorCode": "RPC_ERROR"}, 404)


class FakeOpgg:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, []

    def fetch_records(self, riot_id, region):
        self.calls.append((riot_id, region))
        if self.error:
            raise self.error
        return self.result


def poll_until_lookups_finish(monitor):
    monitor.poll()
    wait(list(monitor._record_futures.values()), timeout=5)
    return monitor.poll()


def test_monitor_looks_up_each_player_once_in_the_background():
    opgg = FakeOpgg({"RANKED_SOLO_5x5": (23, 14)})
    monitor = ClientStateMonitor(rengar=FakeLcu(), opgg=opgg)

    snapshot = poll_until_lookups_finish(monitor)
    monitor.poll()
    monitor.stop()

    assert opgg.calls == [("Smoochie Girl#Gwen", "BR")]
    assert snapshot.champ_select.team[0].rank.winrate == 62


def test_monitor_keeps_wins_only_when_opgg_fails():
    monitor = ClientStateMonitor(rengar=FakeLcu(), opgg=FakeOpgg(error=RuntimeError("down")))

    snapshot = poll_until_lookups_finish(monitor)
    monitor.stop()

    rank = snapshot.champ_select.team[0].rank
    assert (rank.wins, rank.losses, rank.winrate) == (23, None, None)
