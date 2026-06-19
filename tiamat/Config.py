import copy
import json
from pathlib import Path


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

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
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
            config = json.load(config_file)
    except (FileNotFoundError, json.JSONDecodeError):
        config = {}

    config = _merge_defaults(config, DEFAULT_CONFIG)
    save_config(config)
    return config


def save_config(config):
    CONFIG_PATH.write_text(
        json.dumps(config, indent=4) + "\n",
        encoding="utf-8",
    )
