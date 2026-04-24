from Rengar import get_shared_rengar


def change_riotid():
    name = input("Type the new name\n")
    tag = input("Type the new tag\n")

    if tag == "" or name == "":
        print("Insert a valid name/tag.")
        input("\nPress Enter.")
    elif len(name) > 16:
        print("Name length is bigger than 16.")
        input("\nPress Enter.")
    elif len(tag) > 5:
        print("Tag length is bigger than 5")
        input("\nPress Enter.")
    else:
        body = {"gameName": name, "tagLine": tag}
        change = get_shared_rengar().lcu_request(
            "POST", "/lol-summoner/v1/save-alias", body
        )
        print(change.text)
        input("\nPress Enter.")
