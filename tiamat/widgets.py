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
    Feature(1, "AUTOMATIZACION", "Autoaceptar", "Acepta automaticamente la cola cuando aparece una partida.", "toggle"),
    Feature(2, "AUTOMATIZACION", "Instalock", "Selecciona y bloquea tu campeon preferido durante la seleccion.", "configure"),
    Feature(3, "AUTOMATIZACION", "Autoban", "Banea automaticamente el campeon configurado en seleccion.", "configure"),
    Feature(4, "AUTOMATIZACION", "Ragequeue", "Recrea tu lobby preferido y reanuda la cola despues de cada partida.", "configure"),
    Feature(5, "PERSONALIZACION", "Icono de Perfil", "Cambia el icono de perfil visible en tu cuenta de Riot.", "configure"),
    Feature(6, "PERSONALIZACION", "Icono Solo Cliente", "Cambia el icono que solo se muestra dentro del cliente local.", "configure"),
    Feature(7, "PERSONALIZACION", "Fondo de Perfil", "Busca skins y aplica una como fondo de perfil.", "configure"),
    Feature(8, "PERSONALIZACION", "Riot ID", "Cambia el nombre y tag que se muestran en tu cuenta.", "configure"),
    Feature(9, "PERSONALIZACION", "Insignias de Perfil", "Limpia, duplica o aplica insignias bugueadas al perfil.", "configure"),
    Feature(10, "PERSONALIZACION", "Mensaje de Estado", "Actualiza el estado multilinea que ven tus amigos.", "configure"),
    Feature(11, "HERRAMIENTAS", "Lobby Reveal", "Abre la lobby actual de seleccion en Porofessor."),
    Feature(12, "HERRAMIENTAS", "Dodge", "Abandona la seleccion actual sin reiniciar el cliente.", destructive=True),
    Feature(13, "HERRAMIENTAS", "Reiniciar Cliente UX", "Reinicia la interfaz del cliente sin cerrar la partida.", destructive=True),
    Feature(14, "SOCIAL", "Desconectar Chat", "Te muestra offline suspendiendo la conexion del chat de Riot.", "toggle"),
    Feature(15, "SOCIAL", "Eliminar Amigos", "Elimina permanentemente a todos los amigos de la cuenta.", destructive=True),
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
