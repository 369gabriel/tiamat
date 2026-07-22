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
