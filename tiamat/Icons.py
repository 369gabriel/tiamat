from termcolor import colored

from Rengar import get_shared_rengar


def change_profile_icon():
    icon_id = input(colored("Type the icon ID (1 - 500): \n", "magenta"))

    try:
        icon_id = int(icon_id)
    except ValueError:
        print("Please insert a valid number.")
        return

    body = {"profileIconId": icon_id}

    try:
        response = get_shared_rengar().lcu_request(
            "PUT", "/lol-summoner/v1/current-summoner/icon", body
        )
        if response.status_code in (200, 201):
            print(colored(f"Icon sucessfully changed to {icon_id}", "green"))
        else:
            print(f"Error: {response.status_code}")
            print(f"Details: {response.text}")
            input("\nPress Enter.")
    except Exception as e:
        print(f"Error on sending the request: {e}")
        input("\nPress Enter.")


if __name__ == "__main__":
    change_profile_icon()
