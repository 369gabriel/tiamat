from Rengar import Rengar
from termcolor import colored

rengar = Rengar()


def remove_all_friends():
    try:
        # Fetch all friends
        response = rengar.lcu_request("GET", "/lol-friends/v1/friends", "")

        if response.status_code == 200:
            friends = response.json()

            if not friends:
                print(colored("You have no friends to remove.", "yellow"))
                input("\nPress Enter.")
                return

            removed_count = 0
            failed_count = 0

            for friend in friends:
                friend_id = friend.get("summonerId")
                friend_name = friend.get("name", "Unknown")

                try:
                    delete_response = rengar.lcu_request(
                        "DELETE", f"/lol-friends/v1/friends/{friend_id}", ""
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

            input("\nPress Enter.")

        else:
            print(
                colored(
                    f"Error fetching friends. Response code: {response.status_code}",
                    "red",
                )
            )
            input("\nPress Enter.")

    except Exception as e:
        print(colored(f"Error: {str(e)}", "red"))
        input("\nPress Enter.")


if __name__ == "__main__":
    remove_all_friends()
