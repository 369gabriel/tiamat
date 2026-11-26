import io
import math
import time
from dataclasses import dataclass

from rich.console import Console, Group
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Label, ListItem, Static

from ClientState import DISCONNECTED

ACCENT = "#d14b4b"
TEXT = "#e7e7ea"
MUTED = "#8b8b96"
SUCCESS = "#70a87b"
WARNING = "#c9a45c"
INFO = "#7296b8"


@dataclass(frozen=True)
class Feature:
    number: int
    category: str
    title: str
    description: str
    kind: str = "action"
    destructive: bool = False


FEATURES = (
    Feature(1, "AUTOMATION", "Auto Accept", "Automatically accepts ready checks when a match is found.", "toggle"),
    Feature(2, "AUTOMATION", "Instalock", "Locks your preferred champion, with an optional fallback if the main pick is unavailable.", "configure"),
    Feature(3, "AUTOMATION", "AutoBan", "Automatically bans your preferred champion during champion select.", "configure"),
    Feature(4, "AUTOMATION", "Ragequeue", "Creates your preferred lobby and resumes matchmaking after games.", "configure"),
    Feature(5, "CUSTOMIZATION", "Profile Icon", "Changes the profile icon visible on your Riot account.", "configure"),
    Feature(6, "CUSTOMIZATION", "Client-Only Icon", "Changes the icon shown only inside the local League Client.", "configure"),
    Feature(7, "CUSTOMIZATION", "Profile Background", "Searches champion skins and applies one as your profile background.", "configure"),
    Feature(8, "CUSTOMIZATION", "Riot ID", "Changes the game name and tag displayed on your Riot account.", "configure"),
    Feature(9, "CUSTOMIZATION", "Profile Badges", "Clears, duplicates, or applies glitched profile badges.", "configure"),
    Feature(10, "CUSTOMIZATION", "Status Message", "Updates the multiline status displayed to your friends.", "configure"),
    Feature(11, "GAME TOOLS", "Multi-Search", "Opens everyone in the current champion select on your configured multi-search website."),
    Feature(12, "GAME TOOLS", "Restart Client UX", "Restarts the League Client interface without closing the game.", destructive=True),
    Feature(13, "SOCIAL", "Disconnect Chat", "Appears offline by suspending the Riot chat connection.", "toggle"),
    Feature(14, "SOCIAL", "Remove All Friends", "Permanently removes every friend from the account.", destructive=True),
    Feature(15, "SETTINGS", "Configuration", "Configures Multi-Search, automation delays, notifications and updates.", "configure"),
    Feature(16, "SETTINGS", "Help", "Lists every module, what it does and its controls.", "info"),
)

MAX_FEATURE_NUMBER = max(feature.number for feature in FEATURES)
# Modules that work without a League Client connection.
OFFLINE_FEATURES = frozenset({15, 16})


def feature_controls(feature):
    if feature.kind == "toggle":
        controls = "ENTER / SPACE  toggle"
    elif feature.kind == "configure":
        controls = "ENTER  configure"
        if feature.number in {2, 3, 4}:
            controls += "   SPACE  enable / disable"
    elif feature.kind == "info":
        controls = "ENTER  open"
    else:
        controls = "ENTER  run"
    if feature.destructive:
        controls += "   asks for confirmation"
    return controls


class CategoryItem(ListItem):
    def __init__(self, title):
        super().__init__(Static(title, classes="category-label"), disabled=True, classes="category-item")


class FeatureItem(ListItem):
    class ToggleRequested(Message):
        def __init__(self, feature_number):
            super().__init__()
            self.feature_number = feature_number

    def __init__(self, feature):
        self.feature = feature
        super().__init__(id=f"feature-{feature.number}", classes="feature-item")

    def compose(self) -> ComposeResult:
        yield Label(f"{self.feature.number:>2}  {self.feature.title}", classes="feature-name")
        yield Label("", id=f"state-{self.feature.number}", classes="feature-state")

    def on_mouse_down(self, event):
        if event.button == 3:
            event.stop()
            self.suppress_click()
            self.post_message(self.ToggleRequested(self.feature.number))


def _heading(title, detail=None, style=f"bold {TEXT}"):
    heading = Text(title, style=style)
    if detail:
        heading.append("   ")
        heading.append(detail, style=MUTED)
    return heading


def _countdown(deadline_ms, now_ms):
    if deadline_ms is None:
        return None
    seconds = max(0, math.ceil((deadline_ms - now_ms) / 1000))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _automation_block(automations):
    if not automations:
        return []
    grid = Table.grid(padding=(0, 3))
    grid.add_column(style=MUTED, no_wrap=True)
    grid.add_column()
    for label, value in automations:
        active = value not in {"", "OFF", "--"}
        grid.add_row(label, Text(value or "OFF", style=SUCCESS if active else MUTED))
    return [Text(""), Text("ARMED", style=f"bold {MUTED}"), grid]


def _rank_text(entry):
    if entry is None:
        return Text("Unranked", style=MUTED)
    tier = entry.tier.title()
    text = Text(f"{tier} {entry.division}".strip(), style=f"bold {TEXT}")
    text.append(f"  {entry.league_points} LP", style=TEXT)
    games = entry.wins + entry.losses
    if games:
        rate = round(entry.wins * 100 / games)
        text.append(f"   {entry.wins}W {entry.losses}L  {rate}%", style=MUTED)
    return text


def _render_disconnected(automations):
    return [
        _heading("WAITING FOR LEAGUE CLIENT", style=f"bold {WARNING}"),
        Text("Start the League Client; tiamat connects automatically.", style=MUTED),
        *_automation_block(automations),
    ]


def _render_home(snapshot, automations):
    home = snapshot.home
    parts = [_heading(snapshot.phase_label or "HOME"), Text("")]
    if home is not None:
        if home.riot_id:
            parts.append(Text(home.riot_id, style=f"bold {TEXT}"))
        details = []
        if home.level is not None:
            level = f"Level {home.level}"
            if home.level_progress is not None:
                level += f"  ({home.level_progress}% to next)"
            details.append(level)
        if home.chat_status:
            details.append(f"chat {home.chat_status}")
        if details:
            parts.append(Text("   ".join(details), style=MUTED))

        ranks = Table.grid(padding=(0, 3))
        ranks.add_column(style=MUTED, no_wrap=True)
        ranks.add_column()
        ranks.add_row("Solo/Duo", _rank_text(home.solo))
        ranks.add_row("Flex", _rank_text(home.flex))
        parts += [Text(""), Text("RANKED", style=f"bold {MUTED}"), ranks]
    return parts + _automation_block(automations)


TIER_SHORT = {
    "IRON": "I",
    "BRONZE": "B",
    "SILVER": "S",
    "GOLD": "G",
    "PLATINUM": "P",
    "EMERALD": "E",
    "DIAMOND": "D",
    "MASTER": "M",
    "GRANDMASTER": "GM",
    "CHALLENGER": "C",
}
DIVISION_NUMBERS = {"I": "1", "II": "2", "III": "3", "IV": "4"}


def _short_rank(member):
    """Compact elo such as ``G2 45LP`` for a champ-select row."""
    if not member.rank_loaded:
        return Text("…", style=MUTED)
    rank = member.rank
    if rank is None:
        return Text("unranked", style=MUTED)
    tier = TIER_SHORT.get(rank.tier, rank.tier.title())
    division = DIVISION_NUMBERS.get(rank.division, "")
    text = Text(f"{tier}{division}", style=f"bold {TEXT}")
    text.append(f" {rank.league_points}LP", style=TEXT)
    return text


def _short_winrate(member):
    rank = member.rank if member.rank_loaded else None
    if rank is None or rank.winrate is None:
        return Text("")
    rate = rank.winrate
    style = SUCCESS if rate >= 55 else ACCENT if rate <= 45 else TEXT
    text = Text(f"{rate}%", style=style)
    text.append(f" {rank.games}g", style=MUTED)
    return text


def _player_name(member):
    if not member.name:
        return Text("hidden", style=MUTED)
    return Text(member.name, style=f"bold {TEXT}" if member.is_local else TEXT)


def _render_champ_select(snapshot, now_ms):
    view = snapshot.champ_select
    detail = "  ".join(
        part for part in (view.action, _countdown(view.deadline_ms, now_ms)) if part
    )
    parts = [_heading("CHAMP SELECT", detail), Text("")]

    header = f"bold {MUTED}"
    team = Table.grid(padding=(0, 1))
    team.add_column(no_wrap=True)  # local marker
    team.add_column(style=MUTED, no_wrap=True, min_width=4)  # position
    team.add_column(no_wrap=True, overflow="ellipsis", min_width=10)  # riot id
    team.add_column(no_wrap=True, min_width=9)  # elo
    team.add_column(no_wrap=True, min_width=9)  # winrate
    team.add_column(no_wrap=True)  # champion: bold when locked, dim when hovered
    team.add_row(
        "", "", Text("PLAYER", style=header), Text(view.rank_queue, style=header),
        Text("WR", style=header), Text("CHAMPION", style=header),
    )
    for member in view.team:
        marker = Text(">", style=f"bold {ACCENT}") if member.is_local else Text(" ")
        if member.state == "locked":
            champion = Text(member.champion, style=f"bold {TEXT}")
        elif member.champion:
            champion = Text(member.champion, style=f"italic {MUTED}")
        else:
            champion = Text("—", style=MUTED)
        team.add_row(
            marker,
            member.position,
            _player_name(member),
            _short_rank(member),
            _short_winrate(member),
            champion,
        )
    parts.append(team)

    if view.unmatched:
        lobby = Table.grid(padding=(0, 1))
        lobby.add_column(no_wrap=True, overflow="ellipsis", min_width=10)
        lobby.add_column(no_wrap=True, min_width=9)
        lobby.add_column(no_wrap=True)
        for member in view.unmatched:
            lobby.add_row(_player_name(member), _short_rank(member), _short_winrate(member))
        parts += [
            Text(""),
            Text("IN LOBBY  slot unknown", style=header),
            lobby,
        ]

    if view.my_bans or view.their_bans:
        bans = Text("BANS  ", style=header)
        bans.append("  ".join(view.my_bans) or "—", style=TEXT)
        bans.append("   ·   ", style=MUTED)
        bans.append("  ".join(view.their_bans) or "—", style=ACCENT)
        parts += [Text(""), bans]

    return parts


def render_live(snapshot, automations=(), now_ms=None):
    now_ms = time.time() * 1000 if now_ms is None else now_ms
    if not snapshot.connected:
        parts = _render_disconnected(automations)
    elif snapshot.champ_select is not None:
        parts = _render_champ_select(snapshot, now_ms)
    else:
        parts = _render_home(snapshot, automations)
    return Group(*parts)


def render_live_text(snapshot, automations=(), width=70, now_ms=None):
    console = Console(width=width, color_system=None, file=io.StringIO())
    console.print(render_live(snapshot, automations, now_ms))
    return console.file.getvalue()


class LivePanel(Static):
    def __init__(self, **kwargs):
        super().__init__("", **kwargs)
        self.snapshot = DISCONNECTED
        self.automations = ()

    def on_mount(self):
        self.set_interval(1, self._tick)
        self.refresh_view()

    def set_state(self, snapshot=None, automations=None):
        if snapshot is not None:
            self.snapshot = snapshot
        if automations is not None:
            self.automations = tuple(automations)
        self.refresh_view()

    def _tick(self):
        view = self.snapshot.champ_select
        if view is not None and view.deadline_ms is not None:
            self.refresh_view()

    def refresh_view(self):
        self.update(render_live(self.snapshot, self.automations))

    def plain_text(self, width=70):
        return render_live_text(self.snapshot, self.automations, width)
