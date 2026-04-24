from termcolor import colored

from Rengar import get_shared_rengar


def change_status():
    api = get_shared_rengar()

    print(
        colored("Paste your status below. Type 'OK!' on a new line when finished:\n", "magenta")
    )

    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "OK!":
                break
            lines.append(line)
        except EOFError:
            break

    status = "\n".join(lines)

    body = {"statusMessage": status}
    req = api.lcu_request("PUT", "/lol-chat/v1/me", body)
