from dataclasses import dataclass

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Label, ListItem, Static


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
    Feature(2, "AUTOMATION", "Instalock", "Selects and locks your preferred champion during champion select.", "configure"),
    Feature(3, "AUTOMATION", "AutoBan", "Automatically bans your preferred champion during champion select.", "configure"),
    Feature(4, "AUTOMATION", "Ragequeue", "Creates your preferred lobby and resumes matchmaking after games.", "configure"),
    Feature(5, "CUSTOMIZATION", "Profile Icon", "Changes the profile icon visible on your Riot account.", "configure"),
    Feature(6, "CUSTOMIZATION", "Client-Only Icon", "Changes the icon shown only inside the local League Client.", "configure"),
    Feature(7, "CUSTOMIZATION", "Profile Background", "Searches champion skins and applies one as your profile background.", "configure"),
    Feature(8, "CUSTOMIZATION", "Riot ID", "Changes the game name and tag displayed on your Riot account.", "configure"),
    Feature(9, "CUSTOMIZATION", "Profile Badges", "Clears, duplicates, or applies glitched profile badges.", "configure"),
    Feature(10, "CUSTOMIZATION", "Status Message", "Updates the multiline status displayed to your friends.", "configure"),
    Feature(11, "GAME TOOLS", "Lobby Reveal", "Opens the current champion-select lobby with your configured website."),
    Feature(12, "GAME TOOLS", "Dodge", "Leaves the current champion select without restarting the client.", destructive=True),
    Feature(13, "GAME TOOLS", "Restart Client UX", "Restarts the League Client interface without closing the game.", destructive=True),
    Feature(14, "SOCIAL", "Disconnect Chat", "Appears offline by suspending the Riot chat connection.", "toggle"),
    Feature(15, "SOCIAL", "Remove All Friends", "Permanently removes every friend from the account.", destructive=True),
    Feature(16, "SETTINGS", "Configuration", "Configures Lobby Reveal and automation response delays.", "configure"),
)


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
