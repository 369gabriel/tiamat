from Rengar import Rengar


def get_friends(rengar=None):
    api = rengar or Rengar()
    response = api.lcu_request("GET", "/lol-chat/v1/friends", "")
    if response.status_code != 200:
        raise RuntimeError(f"Could not fetch friends (HTTP {response.status_code})")
    return response.json() or []


def remove_all_friends(friends=None, rengar=None):
    api = rengar or Rengar()
    friends = get_friends(api) if friends is None else friends
    removed_count = 0
    failed_count = 0

    for friend in friends:
        friend_id = friend.get("pid")
        if not friend_id:
            failed_count += 1
            continue
        try:
            response = api.lcu_request(
                "DELETE", f"/lol-chat/v1/friends/{friend_id}", ""
            )
            if response.status_code in (200, 204):
                removed_count += 1
            else:
                failed_count += 1
        except Exception:
            failed_count += 1

    return removed_count, failed_count
