from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Select, Static, TextArea
from textual.widgets.option_list import Option


class EnterSelect(Select, inherit_bindings=False):
    BINDINGS = [Binding("enter", "show_overlay", "Show menu", show=False)]


class DialogScreen(ModalScreen):
    def on_key(self, event):
        if event.key == "escape":
            event.stop()
            self.dismiss(None)
            return

        if event.key in {"left", "right"} and isinstance(self.focused, Button):
            buttons = list(self.query(".dialog-actions Button"))
            if len(buttons) < 2:
                return
            event.stop()
            index = buttons.index(self.focused)
            change = -1 if event.key == "left" else 1
            buttons[(index + change) % len(buttons)].focus()
            return

        if event.key == "up" and isinstance(self.focused, Button):
            fields = [
                field
                for field in self.query("Input, Select, TextArea, OptionList")
                if field.display and not field.disabled
            ]
            if fields:
                event.stop()
                fields[-1].focus()
            return

        focused = self.focused
        if event.key in {"down", "up"} and (
            isinstance(focused, Input)
            or (
                isinstance(focused, EnterSelect)
                and not focused.expanded
            )
        ):
            event.stop()
            if event.key == "down":
                self.focus_next()
            else:
                fields = [
                    field
                    for field in self.query("Input, Select, TextArea, OptionList")
                    if field.display and not field.disabled
                ]
                if fields and focused is not fields[0]:
                    self.focus_previous()


class ConfirmScreen(DialogScreen):
    def __init__(self, title, message, confirm_label="Confirm"):
        super().__init__()
        self.dialog_title = title
        self.message = message
        self.confirm_label = confirm_label

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog confirm-dialog"):
            yield Label(self.dialog_title, classes="dialog-title")
            yield Static(self.message, classes="dialog-copy")
            with Horizontal(classes="dialog-actions"):
                yield Button("Cancel", id="cancel", compact=True)
                yield Button(
                    self.confirm_label,
                    id="confirm",
                    variant="error",
                    compact=True,
                )

    def on_mount(self):
        self.query_one("#cancel", Button).focus()

    def on_button_pressed(self, event):
        self.dismiss(event.button.id == "confirm")


class InputFormScreen(DialogScreen):
    def __init__(self, title, description, fields, submit_label="Save", validator=None):
        super().__init__()
        self.dialog_title = title
        self.description = description
        self.fields = fields
        self.submit_label = submit_label
        self.validator = validator

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog form-dialog"):
            yield Label(self.dialog_title, classes="dialog-title")
            yield Static(self.description, classes="dialog-copy")
            for field in self.fields:
                key, label, placeholder, value = field[:4]
                max_length = field[4] if len(field) > 4 else 0
                yield Label(label, classes="field-label")
                yield Input(
                    value=value,
                    placeholder=placeholder,
                    id=f"field-{key}",
                    max_length=max_length,
                )
            yield Label("", id="form-error", classes="form-error")
            with Horizontal(classes="dialog-actions"):
                yield Button("Cancel", id="cancel", compact=True)
                yield Button(
                    self.submit_label,
                    id="submit",
                    variant="primary",
                    compact=True,
                )

    def on_mount(self):
        self.query(Input).first().focus()

    def on_input_submitted(self, _event):
        self.submit()

    def on_button_pressed(self, event):
        if event.button.id == "cancel":
            self.dismiss(None)
        else:
            self.submit()

    def submit(self):
        values = {
            field[0]: self.query_one(f"#field-{field[0]}", Input).value
            for field in self.fields
        }
        if self.validator:
            error = self.validator(values)
            if error:
                self.query_one("#form-error", Label).update(error)
                return
        self.dismiss(values)


class RagequeueScreen(DialogScreen):
    def __init__(self, queue_options, position_options, values, positionless_queue_ids):
        super().__init__()
        self.queue_options = queue_options
        self.position_options = position_options
        self.values = values
        self.positionless_queue_ids = positionless_queue_ids

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog form-dialog"):
            yield Label("Ragequeue", classes="dialog-title")
            yield Static(
                "Choose the lobby and role preferences to use after each game.",
                classes="dialog-copy",
            )
            yield Label("Queue", classes="field-label")
            yield EnterSelect(
                self.queue_options,
                value=self.values[0],
                allow_blank=False,
                id="queue",
                compact=True,
            )
            yield Label("First position", classes="field-label position-field")
            yield EnterSelect(
                self.position_options,
                value=self.values[1] or "TOP",
                allow_blank=False,
                id="first-position",
                classes="position-field",
                compact=True,
            )
            yield Label("Second position", classes="field-label position-field")
            yield EnterSelect(
                self.position_options,
                value=self.values[2] or "JUNGLE",
                allow_blank=False,
                id="second-position",
                classes="position-field",
                compact=True,
            )
            yield Label("", id="form-error", classes="form-error")
            with Horizontal(classes="dialog-actions"):
                yield Button("Cancel", id="cancel", compact=True)
                yield Button(
                    "Save and enable",
                    id="submit",
                    variant="primary",
                    compact=True,
                )

    def on_mount(self):
        self.set_class(
            self.values[0] in self.positionless_queue_ids,
            "positionless-selected",
        )

    def on_select_changed(self, event):
        if event.select.id == "queue":
            self.set_class(
                event.value in self.positionless_queue_ids,
                "positionless-selected",
            )

    def on_button_pressed(self, event):
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        queue_id = self.query_one("#queue", Select).value
        first = self.query_one("#first-position", Select).value
        second = self.query_one("#second-position", Select).value
        if queue_id != 450 and first == second:
            self.query_one("#form-error", Label).update(
                "First and second positions must be different."
            )
            return
        self.dismiss((queue_id, first, second))


class BadgeScreen(DialogScreen):
    MODES = (
        ("Empty all badge slots", "empty"),
        ("Copy the first badge to all slots", "copy"),
        ("Set all slots to a glitched ID", "glitched"),
    )

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog form-dialog"):
            yield Label("Profile Badges", classes="dialog-title")
            yield Static("Choose how the three badge slots should be updated.", classes="dialog-copy")
            yield Label("Mode", classes="field-label")
            yield EnterSelect(
                self.MODES,
                value="empty",
                allow_blank=False,
                id="badge-mode",
                compact=True,
            )
            yield Label("Glitched ID (0-5)", classes="field-label")
            yield Input("0", id="glitched-id")
            yield Label("", id="form-error", classes="form-error")
            with Horizontal(classes="dialog-actions"):
                yield Button("Cancel", id="cancel", compact=True)
                yield Button(
                    "Apply badges",
                    id="submit",
                    variant="primary",
                    compact=True,
                )

    def on_button_pressed(self, event):
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        mode = self.query_one("#badge-mode", Select).value
        glitched_id = self.query_one("#glitched-id", Input).value
        if mode == "glitched":
            try:
                if not 0 <= int(glitched_id) <= 5:
                    raise ValueError
            except ValueError:
                self.query_one("#form-error", Label).update("Enter a number from 0 through 5.")
                return
        self.dismiss((mode, glitched_id))


class StatusScreen(DialogScreen):
    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog status-dialog"):
            yield Label("Status Message", classes="dialog-title")
            yield Static("Write the status shown to friends in the League Client.", classes="dialog-copy")
            yield TextArea(
                placeholder="Enter a status message",
                id="status-editor",
                compact=True,
            )
            with Horizontal(classes="dialog-actions"):
                yield Button("Cancel", id="cancel", compact=True)
                yield Button(
                    "Save status",
                    id="submit",
                    variant="primary",
                    compact=True,
                )

    def on_mount(self):
        self.query_one(TextArea).focus()

    def on_button_pressed(self, event):
        if event.button.id == "cancel":
            self.dismiss(None)
        else:
            self.dismiss(self.query_one(TextArea).text)


class SearchScreen(DialogScreen):
    def __init__(self, title, description, choices, loading_message=""):
        super().__init__()
        self.dialog_title = title
        self.description = description
        self.choices = choices
        self.loading_message = loading_message

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog search-dialog"):
            yield Label(self.dialog_title, classes="dialog-title")
            yield Static(self.description, classes="dialog-copy")
            yield Input(
                placeholder="Type to filter",
                id="search-input",
            )
            yield Static(
                self.loading_message,
                id="search-status",
                classes="search-status",
            )
            yield OptionList(id="search-results", compact=True)
            with Horizontal(classes="dialog-actions"):
                yield Button("Cancel", id="cancel", compact=True)

    def on_mount(self):
        self.update_options("")
        self.query_one(Input).focus()

    def on_input_changed(self, event):
        self.update_options(event.value)

    def set_choices(self, choices):
        self.choices = choices
        self.query_one("#search-status", Static).update("")
        self.update_options(self.query_one(Input).value)

    def set_error(self, error):
        self.query_one("#search-status", Static).update(f"Could not load: {error}")

    def update_options(self, query):
        query = query.strip().lower()
        matches = [choice for choice in self.choices if query in choice[0].lower()][:200]
        options = [Option(label, id=f"value-{index}") for index, (label, _value) in enumerate(matches)]
        option_list = self.query_one(OptionList)
        option_list.clear_options()
        option_list.add_options(options)
        self.filtered_values = [value for _label, value in matches]
        option_list.highlighted = 0 if matches else None

    def on_input_submitted(self, _event):
        option_list = self.query_one(OptionList)
        highlighted = option_list.highlighted
        if highlighted is not None and highlighted < len(self.filtered_values):
            self.dismiss(self.filtered_values[highlighted])

    def on_key(self, event):
        if event.key in {"down", "up"} and self.query_one(Input).has_focus:
            option_list = self.query_one(OptionList)
            if option_list.option_count:
                current = option_list.highlighted or 0
                change = 1 if event.key == "down" else -1
                option_list.highlighted = max(
                    0, min(option_list.option_count - 1, current + change)
                )
            event.stop()
            return

    def on_option_list_option_selected(self, event):
        if event.option_index < len(self.filtered_values):
            self.dismiss(self.filtered_values[event.option_index])

    def on_button_pressed(self, _event):
        self.dismiss(None)
