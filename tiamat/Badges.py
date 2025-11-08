import time

from Rengar import Rengar
from termcolor import colored

# Instanciar Rengar no nível do módulo
rengar = Rengar()


def _get_player_data():
    try:
        resp = rengar.lcu_request(
            "GET", "/lol-challenges/v1/summary-player-data/local-player", ""
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            print(
                colored(
                    f"Error getting player data. Status code: {resp.status_code}", "red"
                )
            )
            return None
    except Exception as e:
        print(colored(f"An exception occurred while getting player data: {e}", "red"))
        return None


def _update_player_preferences(payload):
    try:
        update = rengar.lcu_request(
            "POST", "/lol-challenges/v1/update-player-preferences/", payload
        )
        if update.status_code in (200, 201, 204):
            print(colored("✓ Badges updated successfully.", "green"))
        else:
            print(
                colored(
                    f"Error updating badges. Status code: {update.status_code}", "red"
                )
            )
            print(colored(f"Details: {update.text}", "red"))
    except Exception as e:
        print(colored(f"An exception occurred while updating badges: {e}", "red"))


def change_profile_badges():
    data = _get_player_data()
    if not data:
        time.sleep(0.5)
        return

    # Extrair dados necessários do jogador
    title_id = data.get("title", {}).get("itemId", -1)
    banner_id = data.get("bannerId", "")
    top_challenges = data.get("topChallenges", [])

    # Criar e exibir um menu simples
    print(colored("1. Empty badges", "magenta"))
    print(colored("2. Copy first badge to all", "magenta"))
    print(colored("3. Set all to a glitched ID (0-5)", "magenta"))
    print()

    try:
        selection = int(input(colored("Choose an option: ", "magenta")))
    except ValueError:
        print(colored("Please insert a valid number.", "red"))
        return

    new_ids = None
    if selection == 1:
        new_ids = []
    elif selection == 2:
        if not top_challenges:
            print(colored("No badges found to copy.", "yellow"))
            time.sleep(0.5)
            return
        try:
            first_id = int(top_challenges[0].get("id"))
            new_ids = [first_id] * 3
        except (ValueError, TypeError):
            print(colored("Could not read the ID of the first badge.", "red"))
            time.sleep(0.5)
            return
    elif selection == 3:
        try:
            glitched_id = int(
                input(colored("Enter the glitched badge ID (0-5): ", "magenta"))
            )
            if 0 <= glitched_id <= 5:
                new_ids = [glitched_id] * 3
            else:
                print(colored("Please enter a number between 0 and 5.", "red"))
                return
        except ValueError:
            print(colored("Please insert a valid number.", "red"))
            return
    else:
        print(colored("Invalid option.", "red"))
        return

    if new_ids is None:
        print(colored("An unexpected error occurred while selecting options.", "red"))
        time.sleep(0.5)
        return

    # Montar e enviar o payload
    payload = {"challengeIds": new_ids}
    if title_id != -1:
        payload["title"] = str(title_id)
    if banner_id:
        payload["bannerAccent"] = banner_id

    _update_player_preferences(payload)
    time.sleep(0.5)


if __name__ == "__main__":
    change_profile_badges()
