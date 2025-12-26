from time import sleep

from termcolor import colored

from Rengar import Rengar

rengar = Rengar()


def remove_all_friends():
    try:
        response = rengar.lcu_request("GET", "/lol-chat/v1/friends", "")

        if response.status_code == 200:
            friends = response.json()

            if not friends:
                print(colored("You have no friends to remove.", "yellow"))
                input("\nPress Enter.")
                return

            removed_count = 0
            failed_count = 0

            for friend in friends:
                friend_id = friend.get("pid")
                friend_name = friend.get("name", "Unknown")

                try:
                    delete_response = rengar.lcu_request(
                        "DELETE", f"/lol-chat/v1/friends/{friend_id}", ""
                    )

                    if delete_response.status_code in [200, 204]:
                        removed_count += 1
                        print(colored(f"Removed: {friend_name}", "green"))
                    else:
                        failed_count += 1
                        print(colored(f"Failed to remove: {friend_name}", "red"))

                except Exception as e:
                    failed_count += 1
                    print(colored(f"Error removing {friend_name}: {str(e)}", "red"))

            print(colored(f"\nRemoved {removed_count} friend(s)", "green"))
            if failed_count > 0:
                print(colored(f"Failed to remove {failed_count} friend(s)", "red"))

            sleep(1)

        else:
            print(
                colored(
                    f"Error fetching friends. Response code: {response.status_code}",
                    "red",
                )
            )

    except Exception as e:
        print(colored(f"Error: {str(e)}", "red"))
        input("\nPress Enter.")


if __name__ == "__main__":
    remove_all_friends()
