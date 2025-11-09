import threading
from os import system

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from AutoAccept import autoaccept
from Backgrounds import change_background
from Badges import change_profile_badges
from disconnect_reconnect_chat import Chat
from Dodge import dodge
from Icons import change_profile_icon
from Iconsclient import icon_client
from InstalockAutoban import InstalockAutoban
from RemoveFriends import remove_all_friends
from Rengar import Rengar, check_league_client
from RestartUX import restart
from Reveal import reveal
from Riotidchanger import change_riotid


class MenuOption:
    def __init__(self, title, action, show_state=False, feature_name=""):
        self.title = title
        self.action = action
        self.show_state = show_state
        self.feature_name = feature_name


class LeagueClientTool:
    ASCII_ART = """
    ▄▄▄█████▓ ██▓ ▄▄▄       ███▄ ▄███▓ ▄▄▄     ▄▄▄█████▓
    ▓  ██▒ ▓▒▓██▒▒████▄    ▓██▒▀█▀ ██▒▒████▄   ▓  ██▒ ▓▒
    ▒ ▓██░ ▒░▒██▒▒██  ▀█▄  ▓██    ▓██░▒██  ▀█▄ ▒ ▓██░ ▒░
    ░ ▓██▓ ░ ░██░░██▄▄▄▄██ ▒██    ▒██ ░██▄▄▄▄██░ ▓██▓ ░
      ▒██▒ ░ ░██░ ▓█   ▓██▒▒██▒   ░██▒ ▓█   ▓██▒ ▒██▒ ░
      ▒ ░░   ░▓   ▒▒   ▓▒█░░ ▒░   ░  ░ ▒▒   ▓▒█░ ▒ ░░
        ░     ▒ ░  ▒   ▒▒ ░░  ░      ░  ▒   ▒▒ ░   ░
      ░       ▒ ░  ░   ▒   ░      ░     ░   ▒    ░
              ░        ░  ░       ░         ░  ░
    """

    def __init__(self):
        self.console = Console()
        self.console.print("[red]Starting...[/red]")
        self.rengar = Rengar()
        self.auto_accept = autoaccept()
        self.instalock_autoban = InstalockAutoban()
        self.chat = Chat()
        self._initialize_menu_options()
        self._initialize_threads()

    def _initialize_menu_options(self):
        self.menu_options = {
            1: MenuOption("Icon Changer", change_profile_icon),
            2: MenuOption("Client-Only Icon Changer", icon_client),
            3: MenuOption("Background Changer", change_background),
            4: MenuOption("Lobby Reveal", reveal),
            5: MenuOption(
                "Toggle Auto Accept",
                self.auto_accept.toggle_auto_accept,
                True,
                "auto_accept",
            ),
            6: MenuOption("Dodge", dodge),
            7: MenuOption("Riot ID Changer", change_riotid),
            8: MenuOption("Restart Client UX", restart),
            9: MenuOption(
                "Toggle Instalock",
                self.instalock_autoban.toggle_instalock,
                True,
                "instalock",
            ),
            10: MenuOption(
                "Toggle AutoBan",
                self.instalock_autoban.toggle_auto_ban,
                True,
                "autoban",
            ),
            11: MenuOption("Disconnect Chat", self.chat.toggle_chat, True, "chat"),
            12: MenuOption("Remove All Friends", remove_all_friends),
            13: MenuOption("Change Profile Badges", change_profile_badges),
            99: MenuOption("Exit", self._exit_program),
        }

    def _initialize_threads(self):
        threading.Thread(target=self.auto_accept.monitor_queue, daemon=True).start()

        threading.Thread(
            target=self.instalock_autoban.monitor_champ_select, daemon=True
        ).start()

    def _get_summoner_info(self):
        try:
            summoner_resp = self.rengar.lcu_request(
                "GET", "/lol-summoner/v1/current-summoner", ""
            )
            if summoner_resp.status_code == 200:
                summoner = summoner_resp.json()
                ign = f"{summoner.get('gameName', 'Unknown')}#{summoner.get('tagLine', 'Unknown')}"
                level = summoner.get("summonerLevel", "Unknown")
            else:
                ign = "Unknown"
                level = "Unknown"

            region_resp = self.rengar.lcu_request(
                "GET", "/riotclient/region-locale", ""
            )
            if region_resp.status_code == 200:
                region_data = region_resp.json()
                region = region_data.get("webRegion", "Unknown")
            else:
                region = "Unknown"

            ranked_resp = self.rengar.lcu_request(
                "GET", "/lol-ranked/v1/current-ranked-stats", ""
            )
            if ranked_resp.status_code == 200:
                ranked_data = ranked_resp.json()
                solo_queue = next(
                    (
                        q
                        for q in ranked_data.get("queues", [])
                        if q.get("queueType") == "RANKED_SOLO_5x5"
                    ),
                    None,
                )
                if solo_queue:
                    tier = solo_queue.get("tier", "Unranked")
                    division = solo_queue.get("division", "")
                    lp = solo_queue.get("leaguePoints", 0)
                    elo = (
                        f"{tier} {division} {lp} LP"
                        if tier != "Unranked"
                        else "Unranked"
                    )
                else:
                    elo = "Unranked"
            else:
                elo = "Unknown"

        except Exception as e:
            ign = "Error"
            region = "Error"
            level = "Error"
            elo = "Error"

        return ign, region, level, elo

    def _display_menu(self):
        system("cls")

        ascii_art_centered = Align.center(f"[red]{self.ASCII_ART.strip()}[/red]")
        self.console.print("\n")
        self.console.print(ascii_art_centered)
        self.console.print("\n")

        table = Table(
            title="",
            show_header=True,
            header_style="bold red",
            border_style="red",
            box=None,
            padding=(0, 2),
        )

        for key, option in self.menu_options.items():
            menu_text = option.title

            if option.show_state:
                if key == 9:
                    state = "ON" if self.instalock_autoban.instalock_enabled else "OFF"
                    state_style = "green" if state == "ON" else "red"
                    menu_text += f" ([{state_style}]{state}[/{state_style}]) - Champion: [cyan]{self.instalock_autoban.instalock_champion}[/cyan]"
                elif key == 10:
                    state = "ON" if self.instalock_autoban.auto_ban_enabled else "OFF"
                    state_style = "green" if state == "ON" else "red"
                    menu_text += f" ([{state_style}]{state}[/{state_style}]) - Champion: [cyan]{self.instalock_autoban.auto_ban_champion}[/cyan]"
                else:
                    state = self._get_feature_state(option.feature_name)
                    state_style = "green" if state == "ON" else "red"
                    menu_text += f" ([{state_style}]{state}[/{state_style}])"

            table.add_row(str(key), menu_text)

        centered_table = Align.center(table)
        self.console.print(centered_table)

        return int(self.console.input("\n[red]~-> [/red]"))

    def _get_feature_state(self, feature_name):
        states = {
            "auto_accept": self.auto_accept.auto_accept_enabled,
            "chat": self.chat.chat_state,
        }
        return "ON" if states.get(feature_name, False) else "OFF"

    def _handle_champion_selection(self, option):
        champion_name = self.console.input(
            "[white]Enter the champion name (or 99 to disable): [/white]"
        )
        if option == 9:
            self.instalock_autoban.set_instalock_champion(champion_name)
        else:
            self.instalock_autoban.set_auto_ban_champion(champion_name)

    def _exit_program(self):
        raise KeyboardInterrupt

    def run(self):
        self.console.print("\n[red]Waiting for league client.[/red]\n")
        check_league_client()

        while True:
            try:
                check_league_client()
                option = self._display_menu()

                if option not in self.menu_options:
                    continue

                if option in [9, 10]:
                    self._handle_champion_selection(option)
                else:
                    self.menu_options[option].action()

            except KeyboardInterrupt:
                self._exit_program()
            except Exception as e:
                self.console.print(f"[red]An error occurred: {str(e)}[/red]")
                continue


if __name__ == "__main__":
    client_tool = LeagueClientTool()
    client_tool.run()
