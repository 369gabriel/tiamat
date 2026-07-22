from Rengar import Rengar


def icon_client(icon_id, rengar=None):
    icon_id = int(icon_id)
    if icon_id < 1:
        raise ValueError("El ID del icono debe ser un numero positivo")

    api = rengar or Rengar()
    response = api.lcu_request("PUT", "/lol-chat/v1/me", {"icon": icon_id})
    if response.status_code not in (200, 201):
        raise RuntimeError(f"No se pudo cambiar el icono del cliente (HTTP {response.status_code})")
    return icon_id
