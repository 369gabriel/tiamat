import asyncio

import pytest
from textual.widgets import Button, Input, Select, Static

import app as app_module
from app import TiamatApp
from screens import DelayStepper, SearchScreen, SettingsScreen, StatusScreen
from widgets import FeatureItem


def run_app_test(test, size=(120, 40)):
    async def runner():
        app = TiamatApp(connect_on_mount=False)
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            await test(app, pilot)

    asyncio.run(runner())


def test_app_mounts_grouped_numbered_interface():
    async def check(app, _pilot):
        assert str(app.query_one("#brand", Static).render()) == "tiamat"
        assert len(app.query(FeatureItem)) == 16
        assert app.query_one("#feature-1", FeatureItem).feature.title == "Auto Accept"
        assert app.query_one("#feature-15", FeatureItem).feature.title == "Remove All Friends"
        assert app.query_one("#feature-16", FeatureItem).feature.title == "Configuration"
        assert "League Client not detected" in str(
            app.query_one("#connection", Static).render()
        )
        keybar = str(app.query_one("#keybar", Static).render())
        assert "left click open" in keybar
        assert "right click toggle" in keybar

    run_app_test(check)


def test_module_navigation_does_not_wrap_above_first_row():
    async def check(app, pilot):
        assert app.selected_feature_number == 1
        await pilot.press("up")
        await pilot.pause()
        assert app.selected_feature_number == 1

    run_app_test(check)


def test_right_click_uses_the_same_toggle_path_as_space():
    async def check(app, pilot):
        app.connected = True
        toggled = []
        activated = []
        app.toggle_feature = toggled.append
        app.activate_feature = activated.append

        clicked = await pilot.click("#feature-3", button=3)
        await pilot.pause()

        assert clicked
        assert app.selected_feature_number == 3
        assert toggled == [3]
        assert activated == []

    run_app_test(check)


def test_left_click_runs_module_only_once():
    async def check(app, pilot):
        app.connected = True
        activated = []
        app.activate_feature = activated.append

        clicked = await pilot.click("#feature-5", button=1)
        await pilot.pause()

        assert clicked
        assert app.selected_feature_number == 5
        assert activated == [5]

    run_app_test(check)


def test_multi_digit_shortcut_opens_matching_module():
    async def check(app, pilot):
        app.connected = True
        await pilot.press("1", "0", "enter")
        await pilot.pause()
        assert isinstance(app.screen, StatusScreen)

    run_app_test(check)


def test_settings_open_without_league_and_save_live(monkeypatch):
    saved = []
    monkeypatch.setattr(
        app_module,
        "save_config",
        lambda config: saved.append(config.copy()),
    )

    async def check(app, pilot):
        assert not app.connected
        app.config.setdefault("lobby_reveal", {})["provider"] = "porofessor"
        await pilot.press("1", "6", "enter")
        await pilot.pause()

        assert isinstance(app.screen, SettingsScreen)
        provider = app.screen.query_one("#reveal-provider", Select)
        assert provider.value == "porofessor"
        assert provider.region.height == 3
        assert "Porofessor" in app.export_screenshot()
        auto_accept = app.screen.query_one("#auto-accept-delay", DelayStepper)
        instalock = app.screen.query_one("#instalock-delay", DelayStepper)
        autoban = app.screen.query_one("#autoban-delay", DelayStepper)
        auto_accept.value = 0.4
        instalock.value = 0.8
        autoban.value = 1.2
        app.screen.query_one("#reveal-provider", Select).value = "opgg"

        app.screen.query_one("#submit", Button).focus()
        await pilot.press("enter")
        await pilot.pause()

        assert len(app.screen_stack) == 1
        assert app.config["lobby_reveal"]["provider"] == "opgg"
        assert app.config["auto_accept"]["delay_seconds"] == 0.4
        assert app.config["instalock"]["delay_seconds"] == 0.8
        assert app.config["autoban"]["delay_seconds"] == 1.2
        assert saved

    run_app_test(check, size=(80, 20))


def test_settings_steppers_clamp_and_reset_defaults():
    async def check(app, pilot):
        await pilot.press("1", "6", "enter")
        await pilot.pause()

        auto_accept = app.screen.query_one("#auto-accept-delay", DelayStepper)
        auto_accept.value = 2.0
        auto_accept.focus()
        await pilot.press("right")
        assert auto_accept.value == 2.0
        await pilot.press("home")
        assert auto_accept.value == 0.0
        await pilot.press("right")
        assert auto_accept.value == 0.1
        await pilot.click(auto_accept, offset=(12, 0))
        assert auto_accept.value == 0.2
        await pilot.click(auto_accept, offset=(1, 0))
        assert auto_accept.value == 0.1

        app.screen.query_one("#reset", Button).focus()
        await pilot.press("enter")
        assert auto_accept.value == 0.0
        assert app.screen.query_one("#instalock-delay", DelayStepper).value == 0.3
        assert app.screen.query_one("#autoban-delay", DelayStepper).value == 0.3
        assert app.screen.query_one("#reveal-provider", Select).value == "porofessor"
        assert app.screen.query_one(".dialog").region.bottom <= 20

    run_app_test(check, size=(80, 20))


def test_numeric_shortcut_does_not_also_run_list_selection():
    async def check(app, pilot):
        app.connected = True
        activated = []
        app.activate_feature = activated.append
        app.select_feature(11)

        await pilot.press("1", "1", "enter")
        await pilot.pause()

        assert activated == [11]

    run_app_test(check)


def test_background_screen_opens_before_skins_finish_loading():
    async def check(app, pilot):
        app.connected = True
        action = {}

        def capture_action(
            description,
            worker,
            success_message,
            on_success=None,
            on_error=None,
        ):
            action.update(
                description=description,
                worker=worker,
                success_message=success_message,
                on_success=on_success,
                on_error=on_error,
            )

        app.run_feature_action = capture_action
        await pilot.press("7", "enter")
        await pilot.pause()

        assert isinstance(app.screen, SearchScreen)
        assert "Loading skins" in str(
            app.screen.query_one("#search-status", Static).render()
        )
        assert action["description"] == "Loading skins"

        action["on_success"](
            [{"champion": "Ahri", "name": "Default", "id": "103000"}]
        )
        await pilot.pause()
        assert app.screen.query_one("#search-results").option_count == 1
        assert str(app.screen.query_one("#search-status", Static).render()) == ""

    run_app_test(check)


def test_local_configuration_and_confirmation_screens_mount():
    async def check(app, pilot):
        app.connected = True
        for number in (4, 5, 6, 8, 9, 10, 12, 13):
            await pilot.press(*str(number), "enter")
            await pilot.pause()
            assert len(app.screen_stack) == 2
            await pilot.press("escape")
            await pilot.pause()
            assert len(app.screen_stack) == 1

    run_app_test(check)


def test_search_can_be_completed_from_the_keyboard():
    async def check(app, pilot):
        await pilot.press("/")
        await pilot.press(*"status")
        await pilot.press("enter")
        await pilot.pause()
        assert len(app.screen_stack) == 1
        assert app.selected_feature_number == 10

    run_app_test(check)


def test_invalid_icon_is_kept_in_form_with_inline_error():
    async def check(app, pilot):
        app.connected = True
        await pilot.press("5", "enter")
        await pilot.press("0", "enter")
        await pilot.pause()
        assert len(app.screen_stack) == 2
        assert app.screen.query_one("#field-icon", Input).value == "0"
        assert "positive" in str(app.screen.query_one("#form-error", Static).render())

    run_app_test(check)


def test_icon_and_riot_id_fields_use_visible_inputs():
    async def check(app, pilot):
        app.connected = True

        await pilot.press("5", "enter")
        await pilot.press("2", "9")
        profile_icon = app.screen.query_one("#field-icon", Input)
        assert profile_icon.value == "29"
        assert not profile_icon.has_class("-textual-compact")
        assert profile_icon.region.height == 3

        await pilot.press("escape")
        await pilot.press("6", "enter")
        await pilot.press("4", "2")
        client_icon = app.screen.query_one("#field-icon", Input)
        assert client_icon.value == "42"
        assert client_icon.region.height == 3

        await pilot.press("escape")
        await pilot.press("8", "enter")
        await pilot.press(*"A" * 20)
        await pilot.press("down")
        await pilot.press(*"B" * 10)
        name = app.screen.query_one("#field-name", Input)
        tag = app.screen.query_one("#field-tag", Input)
        assert name.value == "A" * 16
        assert tag.value == "B" * 5
        assert name.max_length == 16
        assert tag.max_length == 5
        assert name.region.height == 3
        assert tag.region.height == 3

    run_app_test(check, size=(80, 20))


@pytest.mark.parametrize("queue_id", [450, 1090, 1100, 1130, 1160])
def test_positionless_queue_configuration_hides_position_fields_on_open(queue_id):
    async def check(app, pilot):
        app.connected = True
        app.ragequeue.queue_id = queue_id
        await pilot.press("4", "enter")
        await pilot.pause()
        assert app.screen.has_class("positionless-selected")

    run_app_test(check)


def test_ragequeue_lists_standard_tft_modes():
    async def check(app, pilot):
        app.connected = True
        await pilot.press("4", "enter")
        await pilot.pause()

        assert {
            ("TFT Normal", 1090),
            ("TFT Ranked", 1100),
            ("TFT Hyper Roll", 1130),
            ("TFT Double Up", 1160),
        }.issubset(set(app.screen.queue_options))

    run_app_test(check)


def test_compact_terminal_uses_single_pane_layout():
    async def check(app, _pilot):
        assert app.has_class("compact")
        assert app.query_one("#module-panel").region.width == 80

    run_app_test(check, size=(80, 24))


def test_ragequeue_arrows_move_focus_without_opening_dropdowns():
    async def check(app, pilot):
        app.connected = True
        await pilot.press("4", "enter")
        await pilot.pause()

        queue = app.screen.query_one("#queue", Select)
        first_position = app.screen.query_one("#first-position", Select)
        assert queue.has_focus

        await pilot.press("up")
        await pilot.pause()
        assert queue.has_focus

        await pilot.press("down")
        await pilot.pause()
        assert not queue.expanded
        assert first_position.has_focus

        await pilot.press("enter")
        await pilot.pause()
        assert first_position.expanded

    run_app_test(check)


def test_search_query_remains_visible_while_filtering():
    async def check(app, pilot):
        await pilot.press("/")
        await pilot.press(*"status")
        await pilot.pause()

        search_input = app.screen.query_one("#search-input", Input)
        assert search_input.value == "status"
        assert not search_input.has_class("-textual-compact")
        assert search_input.region.height == 3

    run_app_test(check)


def test_confirmation_buttons_support_arrow_navigation_in_short_terminal():
    async def check(app, pilot):
        app.connected = True
        await pilot.press("1", "2", "enter")
        await pilot.pause()

        cancel = app.screen.query_one("#cancel", Button)
        confirm = app.screen.query_one("#confirm", Button)
        assert cancel.has_focus

        await pilot.press("right")
        assert confirm.has_focus
        await pilot.press("left")
        assert cancel.has_focus
        assert app.screen.query_one(".dialog").region.bottom <= 20

    run_app_test(check, size=(80, 20))


def test_ragequeue_actions_remain_reachable_in_short_terminal():
    async def check(app, pilot):
        app.connected = True
        await pilot.press("4", "enter")
        await pilot.pause()

        await pilot.press("down", "down", "down")
        cancel = app.screen.query_one("#cancel", Button)
        submit = app.screen.query_one("#submit", Button)
        assert cancel.has_focus

        await pilot.press("right")
        assert submit.has_focus
        assert submit.region.bottom <= 20
        assert app.screen.query_one(".dialog").region.bottom <= 20

        await pilot.press("up")
        assert app.screen.query_one("#second-position", Select).has_focus

    run_app_test(check, size=(80, 20))
