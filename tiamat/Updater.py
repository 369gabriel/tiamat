import re

import requests

from version import __version__


RELEASES_URL = "https://api.github.com/repos/369gabriel/tiamat/releases/latest"
RELEASES_PAGE = "https://github.com/369gabriel/tiamat/releases/latest"
UPDATE_TIMEOUT_SECONDS = 3


def parse_version(value):
    numbers = re.findall(r"\d+", str(value).lstrip("vV").split("-")[0])
    if not numbers:
        return None
    return tuple(int(number) for number in numbers)


def is_newer(latest, current):
    latest_parts = parse_version(latest)
    current_parts = parse_version(current)
    if latest_parts is None or current_parts is None:
        return False
    width = max(len(latest_parts), len(current_parts))
    latest_parts += (0,) * (width - len(latest_parts))
    current_parts += (0,) * (width - len(current_parts))
    return latest_parts > current_parts


def check_for_update(current=__version__, session=requests):
    try:
        response = session.get(
            RELEASES_URL,
            headers={"Accept": "application/vnd.github+json"},
            timeout=UPDATE_TIMEOUT_SECONDS,
        )
        if response.status_code != 200:
            return None
        release = response.json()
    except Exception:
        return None
    if release.get("draft") or release.get("prerelease"):
        return None
    tag = release.get("tag_name", "")
    if not is_newer(tag, current):
        return None
    return tag.lstrip("vV"), release.get("html_url") or RELEASES_PAGE
