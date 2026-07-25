import json
from concurrent.futures import ThreadPoolExecutor

import Config as config_module


def test_concurrent_config_saves_remain_valid_json(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_PATH", config_path)

    configs = [
        {"auto_accept": {"enabled": bool(index % 2)}, "index": index}
        for index in range(20)
    ]
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(config_module.save_config, configs))

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved in configs
    assert not config_path.with_suffix(".json.tmp").exists()


def test_automation_delays_are_clamped_to_safe_range():
    config = {
        "auto_accept": {"delay_seconds": -5},
        "instalock": {"delay_seconds": 1.26},
        "autoban": {"delay_seconds": 99},
    }

    assert config_module.get_automation_delay(config, "auto_accept", 0.0) == 0.0
    assert config_module.get_automation_delay(config, "instalock", 0.3) == 1.3
    assert config_module.get_automation_delay(config, "autoban", 0.3) == 2.0
