import argparse
from collections.abc import Callable, Sequence


def run_terminal():
    try:
        from .app import TiamatApp
    except ImportError:
        from app import TiamatApp

    TiamatApp().run()


def run_web():
    import uvicorn

    try:
        from .web.server import app
    except ImportError:
        from web.server import app

    print()
    print("  Tiamat Web is running at http://127.0.0.1:8000")
    print("  Press Ctrl+C to stop")
    print()
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info",
    )


def choose_interface(input_func: Callable[[str], str] = input) -> str:
    print()
    print("  +---------------------------------------+")
    print("  |                TIAMAT                 |")
    print("  |      Choose how you want to start     |")
    print("  +---------------------------------------+")
    print()
    print("  [1] Web interface")
    print("  [2] Terminal UI")
    print()

    while True:
        try:
            choice = input_func("  Select an interface [1/2] (default: 2): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return "terminal"
        if choice in {"1", "web", "w"}:
            return "web"
        if choice in {"", "2", "terminal", "t", "tui"}:
            return "terminal"
        print("  Invalid option. Enter 1 for Web or 2 for Terminal UI.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tiamat interface launcher")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--web", action="store_true", help="start the Web interface")
    mode.add_argument(
        "--terminal", "--tui", action="store_true", help="start the Terminal UI"
    )
    return parser


def main(argv: Sequence[str] | None = None):
    args = build_parser().parse_args(argv)
    if args.web:
        selected = "web"
    elif args.terminal:
        selected = "terminal"
    else:
        selected = choose_interface()

    if selected == "web":
        run_web()
    else:
        run_terminal()


if __name__ == "__main__":
    main()
