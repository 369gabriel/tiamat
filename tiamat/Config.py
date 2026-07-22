import copy
import json
import sys
import threading
from pathlib import Path


def _config_path():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "config.json"

    return Path(__file__).resolve().parent.parent / "config.json"


CONFIG_PATH = _config_path()
CONFIG_LOCK = threading.RLock()

DEFAULT_CONFIG = {
    "instalock": {
        "enabled": False,
        "champion": "Random",
    },
    "autoban": {
        "enabled": False,
        "champion": "None",
    },
    "auto_accept": {
        "enabled": False,
    },
    "ragequeue": {
        "enabled": False,
        "queue_id": 420,
        "first_position": None,
        "second_position": None,
    },
}


def _merge_defaults(config, defaults):
    merged = copy.deepcopy(defaults)

    if not isinstance(config, dict):
        return merged

    for key, value in config.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_defaults(value, merged[key])
        else:
            merged[key] = value

    return merged


def load_config():
    with CONFIG_LOCK:
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
                config = json.load(config_file)
        except (FileNotFoundError, json.JSONDecodeError):
            config = {}

        config = _merge_defaults(config, DEFAULT_CONFIG)
        save_config(config)
        return config


def save_config(config):
    with CONFIG_LOCK:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = CONFIG_PATH.with_suffix(f"{CONFIG_PATH.suffix}.tmp")
        temporary_path.write_text(
            json.dumps(config, indent=4) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(CONFIG_PATH)
