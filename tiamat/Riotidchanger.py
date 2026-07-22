from Rengar import Rengar


def change_riotid(name, tag, rengar=None):
    name = name.strip()
    tag = tag.strip().lstrip("#")
    if not name or not tag:
        raise ValueError("El nombre y el tag son obligatorios")
    if len(name) > 16:
        raise ValueError("El nombre debe tener 16 caracteres o menos")
    if len(tag) > 5:
        raise ValueError("El tag debe tener 5 caracteres o menos")

    api = rengar or Rengar()
    response = api.lcu_request(
        "POST", "/lol-summoner/v1/save-alias", {"gameName": name, "tagLine": tag}
    )
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f"No se pudo cambiar el Riot ID (HTTP {response.status_code})")
    return f"{name}#{tag}"
