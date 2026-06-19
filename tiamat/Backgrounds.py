import requests
from Rengar import Rengar
from termcolor import colored

class Champ:
    def __init__(self, name="", key=0):
        self.name = name
        self.key = key
        self.skins = []

# Função para buscar as skins de todos os campeões da Community Dragon
def fetch_all_champion_skins():
    url = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/skins.json"
    response = requests.get(url, timeout=10)
    
    if response.status_code != 200:
        print("Error while searching skins.")
        input("\nPress Enter.")
        return None
    
    skins_data = response.json()
    champs = {}

    # Processamento dos dados para organizar por campeão
    for skin_id, current_skin in skins_data.items():
        load_screen_path = current_skin.get("loadScreenPath", "")
        name_start = load_screen_path.find("ASSETS/Characters/") + len("ASSETS/Characters/")
        champ_name = load_screen_path[name_start:load_screen_path.find('/', name_start)]

        name = current_skin.get("name", "")

        skin = {}

        if current_skin.get("isBase", False):
            if champ_name not in champs:
                champs[champ_name] = Champ(name=champ_name)
            
            champ_key = skin_id
            if champ_key.endswith("000"):
                champ_key = champ_key[:-3]
            
            champs[champ_name].key = int(champ_key)
            skin["id"] = skin_id
            skin["name"] = "default"
            champs[champ_name].skins.insert(0, skin)
        else:
            if current_skin.get("questSkinInfo"):
                skin_tiers = current_skin["questSkinInfo"].get("tiers", [])
                for skin_tier in skin_tiers:
                    skin["id"] = skin_tier.get("id", "")
                    skin["name"] = skin_tier.get("name", "")
                    champs[champ_name].skins.append(skin.copy())
            else:
                skin["id"] = skin_id
                skin["name"] = name
                champs[champ_name].skins.append(skin.copy())

    return champs

# Função para procurar skins por nome do campeão ou nome da skin
def search_skins_by_name(champions, search_query):
    found_skins = []
    for champ_name, champ_data in champions.items():
        if search_query.lower() in champ_name.lower():
            found_skins.extend(champ_data.skins)
        else:
            for skin in champ_data.skins:
                if search_query.lower() in skin['name'].lower():
                    found_skins.append(skin)
    return found_skins

# Função para alterar o plano de fundo do perfil
def change_profile_background(skin_id):
    rengar = Rengar()
    body = {
        "key": "backgroundSkinId",
        "value": int(skin_id)  # Certificando que o valor é um inteiro
    }
    
    # Convertendo o corpo para uma string JSON
    body_json = body

    # Fazendo a requisição para alterar o plano de fundo via Rengar
    try:
        response = rengar.lcu_request('POST', "/lol-summoner/v1/current-summoner/summoner-profile", body=body_json)
        if response.status_code == 200:
            print(colored(f"Background changed successfully to skin ID: {skin_id}.", "green"))
        else:
            print(colored(f"Error changing the background. Response code: {response.status_code}", "red"))
            input("\nPress Enter.")
    except Exception as e:
        print(colored(f"Error changing the background: {e}", "red"))
        input("\nPress Enter.")

# Função principal do programa
def change_background():
    print(colored("Fetching skins.", "magenta"))
    champions = fetch_all_champion_skins()

    if champions:
        skin_name = input(colored("Type the champion or skin name: ", "magenta"))
        skins = search_skins_by_name(champions, skin_name)

        if skins:
            print(colored("Found skins:", "magenta"))
            for idx, skin in enumerate(skins):
                print(f"{idx + 1}. {skin['name']} (ID: {skin['id']})")
            
            try:
                choice = int(input(colored("Type the number of the skin to be used: ", "magenta"))) - 1
                if 0 <= choice < len(skins):
                    selected_skin_id = skins[choice]['id']
                    change_profile_background(selected_skin_id)
                else:
                    print("Invalid option.")
                    input("\nPress Enter.")
            except ValueError:
                print("Please insert a valid number.")
                input("\nPress Enter.")
        else:
            print("Skin not found.")
            input("\nPress Enter.")
    else:
        print("Error loading skins.")
        input("\nPress Enter.")

if __name__ == "__main__":
    change_background()
