import main as launcher


def test_interface_chooser_accepts_web_and_terminal():
    assert launcher.choose_interface(lambda _prompt: "1") == "web"
    assert launcher.choose_interface(lambda _prompt: "2") == "terminal"


def test_interface_chooser_defaults_to_terminal():
    assert launcher.choose_interface(lambda _prompt: "") == "terminal"


def test_web_flag_starts_web_mode(monkeypatch):
    started = []
    monkeypatch.setattr(launcher, "run_web", lambda: started.append("web"))
    monkeypatch.setattr(launcher, "run_terminal", lambda: started.append("terminal"))

    launcher.main(["--web"])

    assert started == ["web"]


def test_terminal_flag_starts_terminal_mode(monkeypatch):
    started = []
    monkeypatch.setattr(launcher, "run_web", lambda: started.append("web"))
    monkeypatch.setattr(launcher, "run_terminal", lambda: started.append("terminal"))

    launcher.main(["--terminal"])

    assert started == ["terminal"]
