from importlib import import_module
from os import system

from rich.align import Align
from rich.console import Console
from rich.table import Table


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
        self.rengar = None
        self.auto_accept = None
        self.instalock_autoban = None
        self.chat = None
        self._initialize_menu_options()

    def _initialize_menu_options(self):
        self.menu_options = {
            1: MenuOption(
                "Icon Changer",
                lambda: self._run_module_function("Icons", "change_profile_icon"),
            ),
            2: MenuOption(
                "Client-Only Icon Changer",
                lambda: self._run_module_function("Iconsclient", "icon_client"),
            ),
            3: MenuOption(
                "Background Changer",
                lambda: self._run_module_function("Backgrounds", "change_background"),
            ),
            4: MenuOption(
                "Lobby Reveal",
                lambda: self._run_module_function("Reveal", "reveal"),
            ),
            5: MenuOption(
                "Toggle Auto Accept",
                self._toggle_auto_accept,
                True,
                "auto_accept",
            ),
            6: MenuOption(
                "Dodge",
                lambda: self._run_module_function("Dodge", "dodge"),
            ),
            7: MenuOption(
                "Riot ID Changer",
                lambda: self._run_module_function("Riotidchanger", "change_riotid"),
            ),
            8: MenuOption(
                "Restart Client UX",
                lambda: self._run_module_function("RestartUX", "restart"),
            ),
            9: MenuOption("Toggle Instalock", self._handle_instalock, True, "instalock"),
            10: MenuOption("Toggle AutoBan", self._handle_autoban, True, "autoban"),
            11: MenuOption("Disconnect Chat", self._toggle_chat, True, "chat"),
            12: MenuOption(
                "Remove All Friends",
                lambda: self._run_module_function("RemoveFriends", "remove_all_friends"),
            ),
            13: MenuOption(
                "Change Profile Badges",
                lambda: self._run_module_function("Badges", "change_profile_badges"),
            ),
            14: MenuOption(
                "Change Status",
                lambda: self._run_module_function("StatusChanger", "change_status"),
            ),
            99: MenuOption("Exit", self._exit_program),
        }

    def _get_rengar(self):
        if self.rengar is None:
            self.rengar = import_module("Rengar").get_shared_rengar()
        return self.rengar

    def _wait_for_client(self):
        import_module("Rengar").check_league_client()

    def _get_auto_accept(self):
        if self.auto_accept is None:
            self.auto_accept = import_module("AutoAccept").autoaccept()
        return self.auto_accept

    def _get_instalock_autoban(self):
        if self.instalock_autoban is None:
            self.instalock_autoban = import_module("InstalockAutoban").InstalockAutoban()
        return self.instalock_autoban

    def _get_chat(self):
        if self.chat is None:
            self.chat = import_module("disconnect_reconnect_chat").Chat()
        return self.chat

    def _run_module_function(self, module_name, function_name):
        module = import_module(module_name)
        getattr(module, function_name)()

    def _toggle_auto_accept(self):
        self._get_auto_accept().toggle_auto_accept()

    def _toggle_chat(self):
        self._get_chat().toggle_chat()

    def _handle_instalock(self):
        self._handle_champion_selection(9)

    def _handle_autoban(self):
        self._handle_champion_selection(10)

    def _get_summoner_info(self):
        try:
            rengar = self._get_rengar()
            summoner_resp = rengar.lcu_request("GET", "/lol-summoner/v1/current-summoner", "")
            if summoner_resp.status_code == 200:
                summoner = summoner_resp.json()
                ign = (
                    f"{summoner.get('gameName', 'Unknown')}"
                    f"#{summoner.get('tagLine', 'Unknown')}"
                )
                level = summoner.get("summonerLevel", "Unknown")
            else:
                ign = "Unknown"
                level = "Unknown"

            region_resp = rengar.lcu_request("GET", "/riotclient/region-locale", "")
            if region_resp.status_code == 200:
                region_data = region_resp.json()
                region = region_data.get("webRegion", "Unknown")
            else:
                region = "Unknown"

            ranked_resp = rengar.lcu_request(
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
        except Exception:
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

        instalock = self.instalock_autoban

        for key, option in self.menu_options.items():
            menu_text = option.title

            if option.show_state:
                if key == 9:
                    state = (
                        "ON"
                        if instalock is not None and instalock.instalock_enabled
                        else "OFF"
                    )
                    state_style = "green" if state == "ON" else "red"
                    champion = (
                        instalock.instalock_champion if instalock is not None else "Random"
                    )
                    menu_text += (
                        f" ([{state_style}]{state}[/{state_style}])"
                        f" - Champion: [cyan]{champion}[/cyan]"
                    )
                elif key == 10:
                    state = (
                        "ON"
                        if instalock is not None and instalock.auto_ban_enabled
                        else "OFF"
                    )
                    state_style = "green" if state == "ON" else "red"
                    champion = (
                        instalock.auto_ban_champion if instalock is not None else "None"
                    )
                    menu_text += (
                        f" ([{state_style}]{state}[/{state_style}])"
                        f" - Champion: [cyan]{champion}[/cyan]"
                    )
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
            "auto_accept": (
                self.auto_accept.auto_accept_enabled if self.auto_accept is not None else False
            ),
            "chat": self.chat.chat_state if self.chat is not None else False,
        }
        return "ON" if states.get(feature_name, False) else "OFF"

    def _handle_champion_selection(self, option):
        champion_name = self.console.input(
            "[white]Enter the champion name (or 99 to disable): [/white]"
        )
        instalock = self._get_instalock_autoban()
        if option == 9:
            instalock.set_instalock_champion(champion_name)
        else:
            instalock.set_auto_ban_champion(champion_name)

    def _exit_program(self):
        raise KeyboardInterrupt

    def run(self):
        self.console.print("\n[red]Waiting for league client.[/red]\n")
        self._wait_for_client()

        while True:
            try:
                option = self._display_menu()

                if option not in self.menu_options:
                    continue

                self.menu_options[option].action()
            except KeyboardInterrupt:
                self._exit_program()
            except Exception as e:
                self.console.print(f"[red]An error occurred: {str(e)}[/red]")
                continue


if __name__ == "__main__":
    client_tool = LeagueClientTool()
    client_tool.run()
