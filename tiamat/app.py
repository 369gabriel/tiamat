import threading
import time
from datetime import datetime

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Label, ListView, RichLog, Static

from AutoAccept import AutoAccept
from Backgrounds import change_profile_background, fetch_all_champion_skins
from Badges import change_profile_badges
from Config import load_config
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
from screens import (
    BadgeScreen,
    ConfirmScreen,
    InputFormScreen,
    RagequeueScreen,
    SearchScreen,
    StatusScreen,
)
from StatusChanger import change_status
from widgets import FEATURES, CategoryItem, FeatureItem


class TiamatApp(App):
    CSS_PATH = "tiamat.tcss"
    TITLE = "tiamat"
    ENABLE_COMMAND_PALETTE = False
    STATUS_LABELS = {
        "ON": "ACTIVO",
        "OFF": "INACTIVO",
        "--": "--",
        "Ready": "LISTO",
    }

    def __init__(self, connect_on_mount=True):
        super().__init__()
        self.connect_on_mount = connect_on_mount
        self.config = load_config()
        self.connected = False
        self.account_text = "Cliente de League no detectado"
        self.chat = None
        self.shortcut_buffer = ""
        self.selected_feature_number = 1
        self._stopping = False
        self._monitors_started = False
        self._last_events = {}
        self._ui_thread_id = None
        self._mouse_toggle_number = None
        self.auto_accept = AutoAccept(self.config, self.receive_automation_event)
        self.champion_automation = InstalockAutoban(
            self.config, self.receive_automation_event
        )
        self.ragequeue = RageQueue(self.config, self.receive_automation_event)

    def compose(self) -> ComposeResult:
        with Horizontal(id="header"):
            with Vertical(id="brand-block"):
                yield Static("TIAMAT", id="brand")
                yield Static("Panel tactico para el cliente de League", id="brand-subtitle")
            yield Static(self.account_text, id="connection")

        feature_items = []
        category = None
        for feature in FEATURES:
            if feature.category != category:
                category = feature.category
                feature_items.append(CategoryItem(category))
            feature_items.append(FeatureItem(feature))

        with Horizontal(id="workspace"):
            with Vertical(id="module-panel"):
                yield Static("MODULOS", classes="panel-heading")
                yield ListView(*feature_items, initial_index=1, id="feature-list")
            with Vertical(id="detail-panel"):
                yield Static("AUTOACEPTAR", id="detail-title")
                yield Static("", id="detail-kicker")
                yield Static("", id="detail-description")
                with Horizontal(id="detail-cards"):
                    yield Static("", id="detail-state-card", classes="detail-card")
                    yield Static("", id="detail-client-card", classes="detail-card")
                yield Static("", id="detail-actions")

        with Vertical(id="activity-panel"):
            yield Static("ACTIVIDAD", classes="panel-heading")
            yield RichLog(id="activity-log", markup=True, wrap=True, max_lines=100)

        yield Static("", id="shortcut-bar")
        yield Static(
            "arriba/abajo navegar   enter abrir   espacio alternar   / buscar   ? ayuda   q salir\n"
            "click izquierdo abrir   click derecho alternar",
            id="keybar",
        )

    def on_mount(self):
        self._ui_thread_id = threading.get_ident()
        self.refresh_feature_states()
        self.show_feature(1)
        self.add_activity("system", "Tiamat iniciado")
        if self.connect_on_mount:
            self.run_worker(
                self.connection_loop,
                name="client-connection",
                group="connection",
                thread=True,
                exit_on_error=False,
            )

    def on_resize(self, event):
        self.set_class(event.size.width <= 85, "compact")

    def on_unmount(self):
        self._stopping = True
        self.auto_accept.stop()
        self.champion_automation.stop()
        self.ragequeue.stop()

    def connection_loop(self):
        previous_credentials = (None, None)
        while not self._stopping:
            port, token = find_league_client_credentials()
            credentials = (port, token) if port and token else (None, None)
            if credentials != (None, None) and credentials != previous_credentials:
                try:
                    api = Rengar()
                    account_text = self.read_account_text(api)
                    try:
                        chat = Chat(api)
                    except Exception as error:
                        chat = None
                        self.call_from_thread(
                            self.add_activity,
                            "warning",
                            f"Estado del chat no disponible: {error}",
                        )
                    self.call_from_thread(
                        self.client_connected, account_text, chat, api
                    )
                except Exception as error:
                    self.call_from_thread(
                        self.add_activity, "error", f"Conexion del cliente: {error}"
                    )
                    credentials = (None, None)
            elif previous_credentials != (None, None) and credentials == (None, None):
                self.call_from_thread(self.client_disconnected)
            previous_credentials = credentials
            time.sleep(2)

    @staticmethod
    def read_account_text(api):
        summoner_response = api.lcu_request(
            "GET", "/lol-summoner/v1/current-summoner", ""
        )
        region_response = api.lcu_request("GET", "/riotclient/region-locale", "")
        if summoner_response.status_code != 200:
            return "Cliente de League conectado"
        summoner = summoner_response.json()
        riot_id = f"{summoner.get('gameName', 'Unknown')}#{summoner.get('tagLine', 'Unknown')}"
        region = ""
        if region_response.status_code == 200:
            region = region_response.json().get("webRegion", "").upper()
        return f"conectado  {riot_id}" + (f"  {region}" if region else "")

    def client_connected(self, account_text, chat, api):
        self.connected = True
        self.chat = chat
        self.auto_accept.rengar = api
        self.champion_automation.rengar = api
        self.ragequeue.rengar = api
        self.account_text = account_text
        connection = self.query_one("#connection", Static)
        connection.update(account_text)
        connection.set_class(True, "connected")
        self.add_activity("system", "Conectado al cliente de League")
        self.refresh_feature_states()
        if not self._monitors_started:
            self._monitors_started = True
            self.run_worker(
                self.auto_accept.monitor_queue,
                name="auto-accept-monitor",
                group="monitors",
                thread=True,
                exit_on_error=False,
            )
            self.run_worker(
                self.champion_automation.monitor_champ_select,
                name="champion-select-monitor",
                group="monitors",
                thread=True,
                exit_on_error=False,
            )
            self.run_worker(
                self.ragequeue.monitor_gameflow,
                name="ragequeue-monitor",
                group="monitors",
                thread=True,
                exit_on_error=False,
            )

    def client_disconnected(self):
        self.connected = False
        self.chat = None
        self.account_text = "Cliente de League no detectado"
        connection = self.query_one("#connection", Static)
        connection.update(self.account_text)
        connection.set_class(False, "connected")
        self.add_activity("warning", "Cliente desconectado; esperando reconexion")
        self.refresh_feature_states()

    def receive_automation_event(self, level, message):
        if self._stopping or not self.is_mounted:
            return
        if threading.get_ident() == self._ui_thread_id:
            self.add_activity(level, message)
            return
        try:
            self.call_from_thread(self.add_activity, level, message)
        except RuntimeError:
            return

    def add_activity(self, level, message):
        now = time.monotonic()
        event_key = (level, message)
        if level == "error" and now - self._last_events.get(event_key, 0) < 15:
            return
        self._last_events[event_key] = now
        styles = {
            "success": "green",
            "error": "red",
            "warning": "yellow",
            "system": "bright_black",
            "info": "cyan",
        }
        style = styles.get(level, "white")
        timestamp = datetime.now().strftime("%H:%M")
        self.query_one("#activity-log", RichLog).write(
            f"[bright_black]{timestamp}[/]  [{style}]{escape(level):<7}[/]  {escape(str(message))}"
        )

    def feature_state(self, number):
        if number == 1:
            return "ON" if self.auto_accept.auto_accept_enabled else "OFF"
        if number == 2:
            if not self.champion_automation.instalock_enabled:
                return "OFF"
            return self.champion_automation.instalock_champion
        if number == 3:
            if not self.champion_automation.auto_ban_enabled:
                return "OFF"
            return self.champion_automation.auto_ban_champion
        if number == 4:
            return self.ragequeue.queue_name if self.ragequeue.enabled else "OFF"
        if number == 14:
            return self.chat.return_state() if self.chat else "--"
        return ""

    def refresh_feature_states(self):
        if not self.is_mounted:
            return
        for feature in FEATURES:
            state = self.feature_state(feature.number)
            label = self.query_one(f"#state-{feature.number}", Label)
            label.update(self.translate_state(state))
            label.set_class(state not in {"", "OFF", "--"}, "state-active")
        self.show_feature(self.selected_feature_number)

    def show_feature(self, number):
        feature = next(item for item in FEATURES if item.number == number)
        self.selected_feature_number = number
        self.query_one("#detail-title", Static).update(feature.title.upper())
        self.query_one("#detail-kicker", Static).update(
            f"Modulo {feature.number:02d}  {feature.category}"
        )
        self.query_one("#detail-description", Static).update(feature.description)

        state = self.feature_state(number)
        state_text = self.translate_state(state or "Ready")
        connected_text = "Disponible" if self.connected else "Esperando cliente"
        self.query_one("#detail-state-card", Static).update(
            f"ESTADO\n{state_text}"
        )
        self.query_one("#detail-client-card", Static).update(
            f"CLIENTE\n{connected_text}"
        )

        if feature.kind == "toggle":
            actions = "ENTER  alternar\nSPACE  alternar"
        elif feature.kind == "configure":
            actions = "ENTER  configurar"
            if number in {2, 3, 4}:
                actions += "\nSPACE  activar / desactivar"
        else:
            actions = "ENTER  ejecutar"
        if feature.destructive:
            actions += "\nRequiere confirmacion"
        self.query_one("#detail-actions", Static).update(actions)

    def translate_state(self, value):
        return self.STATUS_LABELS.get(value, value)

    def on_list_view_highlighted(self, event):
        if isinstance(event.item, FeatureItem):
            self.show_feature(event.item.feature.number)

    def on_list_view_selected(self, event):
        if isinstance(event.item, FeatureItem):
            number = event.item.feature.number
            if self._mouse_toggle_number == number:
                self._mouse_toggle_number = None
                return
            self.activate_feature(number)

    def on_feature_item_toggle_requested(self, message):
        self._mouse_toggle_number = message.feature_number
        self.set_timer(0.25, self.clear_mouse_toggle_suppression)
        self.select_feature(message.feature_number)
        self.toggle_feature(message.feature_number)

    def clear_mouse_toggle_suppression(self):
        self._mouse_toggle_number = None

    def on_key(self, event):
        if len(self.screen_stack) > 1:
            return

        key = event.key
        if len(key) == 1 and key.isdigit():
            event.stop()
            self.append_shortcut(key)
            return
        if key == "escape" and self.shortcut_buffer:
            event.stop()
            self.clear_shortcut()
            return
        if key == "enter" and self.shortcut_buffer:
            event.stop()
            number = int(self.shortcut_buffer)
            self.clear_shortcut()
            if 1 <= number <= 15:
                self.select_feature(number)
                self.activate_feature(number)
            elif number == 99:
                self.exit()
            return
        if key == "space":
            event.stop()
            self.toggle_feature(self.selected_feature_number)
        elif key == "j":
            event.stop()
            self.query_one(ListView).action_cursor_down()
        elif key == "k":
            event.stop()
            self.query_one(ListView).action_cursor_up()
        elif key in {"/", "slash"}:
            event.stop()
            choices = [
                (f"{feature.number:>2}  {feature.title}", feature.number)
                for feature in FEATURES
            ]
            self.push_screen(
                SearchScreen(
                    "Buscar modulo",
                    "Busca por nombre o numero del modulo.",
                    choices,
                ),
                self.select_feature,
            )
        elif key in {"?", "question_mark"}:
            event.stop()
            self.notify(
                "Usa flechas o j/k para navegar. Escribe un numero de modulo y presiona Enter para ejecutarlo. "
                "Click izquierdo abre el modulo; click derecho lo alterna.",
                title="Ayuda de teclado",
                timeout=6,
            )
        elif key == "q":
            event.stop()
            self.exit()

    def append_shortcut(self, digit):
        valid_commands = [str(number) for number in range(1, 16)] + ["99"]
        candidate = self.shortcut_buffer + digit
        if not any(command.startswith(candidate) for command in valid_commands):
            candidate = digit
        self.shortcut_buffer = candidate
        exact = next(
            (feature.title for feature in FEATURES if str(feature.number) == candidate),
            "Salir" if candidate == "99" else "",
        )
        self.query_one("#shortcut-bar", Static).update(
            f"Atajo: {candidate}_" + (f"    {exact}" if exact else "")
        )
        self.set_class(True, "entering-shortcut")

    def clear_shortcut(self):
        self.shortcut_buffer = ""
        self.query_one("#shortcut-bar", Static).update("")
        self.set_class(False, "entering-shortcut")

    def select_feature(self, number):
        if number is None:
            return
        feature_item = self.query_one(f"#feature-{number}", FeatureItem)
        feature_list = self.query_one("#feature-list", ListView)
        feature_list.index = list(feature_list.children).index(feature_item)
        feature_list.focus()
        self.show_feature(number)

    def require_connection(self):
        if self.connected:
            return True
        self.add_activity("warning", "Abre el cliente de League antes de usar este modulo")
        self.notify("El cliente de League no esta conectado", severity="warning")
        return False

    def run_feature_action(self, description, action, success_message, on_success=None):
        if not self.require_connection():
            return
        self.add_activity("info", description)

        def work():
            try:
                result = action()
            except Exception as error:
                self.call_from_thread(self.action_failed, description, error)
            else:
                self.call_from_thread(
                    self.action_succeeded,
                    result,
                    success_message,
                    on_success,
                )

        self.run_worker(
            work,
            name=description,
            group="actions",
            thread=True,
            exit_on_error=False,
        )

    def action_failed(self, description, error):
        self.add_activity("error", f"{description}: {error}")
        self.notify(str(error), title=description, severity="error")

    def action_succeeded(self, result, success_message, on_success):
        message = success_message(result) if callable(success_message) else success_message
        if message:
            self.add_activity("success", message)
            self.notify(message, severity="information")
        if on_success:
            on_success(result)
        self.refresh_feature_states()

    def activate_feature(self, number):
        if not self.require_connection():
            return
        actions = {
            1: self.toggle_auto_accept,
            2: lambda: self.open_champion_search("instalock"),
            3: lambda: self.open_champion_search("autoban"),
            4: self.open_ragequeue,
            5: self.open_profile_icon,
            6: self.open_client_icon,
            7: self.open_background_search,
            8: self.open_riot_id,
            9: self.open_badges,
            10: self.open_status,
            11: self.run_lobby_reveal,
            12: self.confirm_dodge,
            13: self.confirm_restart,
            14: self.toggle_chat,
            15: self.prepare_remove_friends,
        }
        actions[number]()

    def toggle_feature(self, number):
        if not self.require_connection():
            return
        if number == 1:
            self.toggle_auto_accept()
        elif number == 2:
            if self.champion_automation.instalock_enabled:
                self.champion_automation.toggle_instalock()
                self.refresh_feature_states()
            else:
                self.open_champion_search("instalock")
        elif number == 3:
            if self.champion_automation.auto_ban_enabled:
                self.champion_automation.toggle_auto_ban()
                self.refresh_feature_states()
            else:
                self.open_champion_search("autoban")
        elif number == 4:
            if self.ragequeue.enabled:
                self.ragequeue.disable()
                self.refresh_feature_states()
            else:
                self.open_ragequeue()
        elif number == 14:
            self.toggle_chat()

    def toggle_auto_accept(self):
        self.auto_accept.toggle_auto_accept()
        self.refresh_feature_states()

    def open_champion_search(self, mode):
        def show_search(champions):
            choices = [("Random", "Random")] if mode == "instalock" else []
            choices.extend((name.title(), name.title()) for name in champions)
            title = "Campeon de Instalock" if mode == "instalock" else "Campeon de Autoban"
            self.push_screen(
                SearchScreen(
                    title,
                    "Escribe el nombre del campeon y luego selecciona uno.",
                    choices,
                ),
                lambda champion: self.save_champion(mode, champion),
            )

        self.run_feature_action(
            "Cargando campeones",
            self.champion_automation.update_champion_list,
            "",
            show_search,
        )

    def save_champion(self, mode, champion):
        if not champion:
            return
        setter = (
            self.champion_automation.set_instalock_champion
            if mode == "instalock"
            else self.champion_automation.set_auto_ban_champion
        )
        self.run_feature_action(
            f"Configurando {mode}",
            lambda: setter(champion),
            lambda value: f"{mode.title()} configurado para {value}",
        )

    def open_ragequeue(self):
        queues = [(name, queue_id) for name, queue_id in RageQueue.QUEUE_TYPES.values()]
        positions = [
            (name, position) for name, position in RageQueue.POSITION_TYPES.values()
        ]
        values = (
            self.ragequeue.queue_id,
            self.ragequeue.first_position,
            self.ragequeue.second_position,
        )
        self.push_screen(
            RagequeueScreen(queues, positions, values), self.save_ragequeue
        )

    def save_ragequeue(self, values):
        if not values:
            return
        queue_id, first, second = values
        if queue_id == 450:
            action = lambda: self.ragequeue.set_queue(queue_id)
        else:
            action = lambda: self.ragequeue.configure(queue_id, first, second)
        self.run_feature_action(
            "Guardando Ragequeue",
            action,
            lambda _result: f"Ragequeue activado para {self.ragequeue.queue_name}",
        )

    def open_profile_icon(self):
        self.push_screen(
            InputFormScreen(
                "Icono de Perfil",
                "Ingresa el ID numerico del icono de perfil.",
                [("icon", "ID del icono", "Por ejemplo: 29", "")],
                "Cambiar icono",
                self.validate_icon_form,
            ),
            lambda values: self.submit_icon(values, client_only=False),
        )

    def open_client_icon(self):
        self.push_screen(
            InputFormScreen(
                "Icono Solo Cliente",
                "Ingresa un ID de icono para mostrarlo solo dentro del cliente.",
                [("icon", "ID del icono", "Por ejemplo: 29", "")],
                "Cambiar icono",
                self.validate_icon_form,
            ),
            lambda values: self.submit_icon(values, client_only=True),
        )

    def submit_icon(self, values, client_only):
        if not values:
            return
        action = icon_client if client_only else change_profile_icon
        label = "Icono del cliente" if client_only else "Icono de perfil"
        self.run_feature_action(
            f"Cambiando {label.lower()}",
            lambda: action(values["icon"]),
            lambda icon_id: f"{label} cambiado a {icon_id}",
        )

    def open_background_search(self):
        def show_skins(skins):
            choices = [
                (f"{skin['champion']} - {skin['name']}  [{skin['id']}]", skin)
                for skin in skins
            ]
            self.push_screen(
                SearchScreen(
                    "Fondo de Perfil",
                    "Busca por campeon o por nombre de skin.",
                    choices,
                ),
                self.save_background,
            )

        self.run_feature_action("Cargando skins", fetch_all_champion_skins, "", show_skins)

    def save_background(self, skin):
        if not skin:
            return
        self.run_feature_action(
            "Cambiando fondo de perfil",
            lambda: change_profile_background(skin["id"]),
            f"Fondo de perfil cambiado a {skin['champion']} - {skin['name']}",
        )

    def open_riot_id(self):
        self.push_screen(
            InputFormScreen(
                "Riot ID",
                "Ingresa el nuevo nombre y tag.",
                [
                    ("name", "Nombre", "Hasta 16 caracteres", "", 16),
                    ("tag", "Tag", "Hasta 5 caracteres", "", 5),
                ],
                "Cambiar Riot ID",
                self.validate_riot_id_form,
            ),
            self.save_riot_id,
        )

    @staticmethod
    def validate_icon_form(values):
        try:
            if int(values["icon"]) < 1:
                raise ValueError
        except ValueError:
            return "El ID del icono debe ser un numero positivo."
        return ""

    @staticmethod
    def validate_riot_id_form(values):
        name = values["name"].strip()
        tag = values["tag"].strip().lstrip("#")
        if not name or not tag:
            return "El nombre y el tag son obligatorios."
        if len(name) > 16:
            return "El nombre debe tener 16 caracteres o menos."
        if len(tag) > 5:
            return "El tag debe tener 5 caracteres o menos."
        return ""

    def save_riot_id(self, values):
        if not values:
            return
        self.run_feature_action(
            "Cambiando Riot ID",
            lambda: change_riotid(values["name"], values["tag"]),
            lambda riot_id: f"Riot ID cambiado a {riot_id}",
        )

    def open_badges(self):
        self.push_screen(BadgeScreen(), self.save_badges)

    def save_badges(self, values):
        if not values:
            return
        mode, glitched_id = values
        self.run_feature_action(
            "Actualizando insignias de perfil",
            lambda: change_profile_badges(mode, glitched_id),
            "Insignias de perfil actualizadas",
        )

    def open_status(self):
        self.push_screen(StatusScreen(), self.save_status)

    def save_status(self, status):
        if status is None:
            return
        self.run_feature_action(
            "Actualizando mensaje de estado",
            lambda: change_status(status),
            "Mensaje de estado actualizado",
        )

    def run_lobby_reveal(self):
        self.run_feature_action("Revelando lobby", reveal, "Lobby abierta en tu navegador")

    def confirm_dodge(self):
        self.push_screen(
            ConfirmScreen(
                "Dodge de Seleccion",
                "Esto saldra inmediatamente de la seleccion actual.",
                "Hacer dodge",
            ),
            lambda confirmed: self.run_feature_action(
                "Haciendo dodge en seleccion", dodge, "Seleccion abandonada"
            )
            if confirmed
            else None,
        )

    def confirm_restart(self):
        self.push_screen(
            ConfirmScreen(
                "Reiniciar Cliente UX",
                "La interfaz del cliente se cerrara un momento y luego volvera.",
                "Reiniciar UX",
            ),
            lambda confirmed: self.run_feature_action(
                "Reiniciando Cliente UX", restart, "Reinicio de UX solicitado"
            )
            if confirmed
            else None,
        )

    def toggle_chat(self):
        if self.chat is None:
            self.add_activity("warning", "El chat de Riot no esta disponible ahora mismo")
            self.notify("El chat de Riot no esta disponible ahora mismo", severity="warning")
            return
        self.run_feature_action(
            "Cambiando conexion del chat",
            self.chat.toggle_chat,
            lambda disconnected: "Chat desconectado" if disconnected else "Chat reconectado",
        )

    def prepare_remove_friends(self):
        def confirm(friends):
            count = len(friends)
            if count == 0:
                self.add_activity("info", "No hay amigos para eliminar")
                self.notify("No hay amigos para eliminar")
                return
            self.push_screen(
                ConfirmScreen(
                    "Eliminar Todos los Amigos",
                    f"Esto eliminara permanentemente a los {count} amigos de la cuenta.",
                    f"Eliminar {count}",
                ),
                lambda confirmed: self.remove_friends(friends) if confirmed else None,
            )

        self.run_feature_action("Leyendo lista de amigos", get_friends, "", confirm)

    def remove_friends(self, friends):
        self.run_feature_action(
            "Eliminando todos los amigos",
            lambda: remove_all_friends(friends),
            lambda counts: f"Se eliminaron {counts[0]} amigos; {counts[1]} fallaron",
        )
