import pytest

from Backgrounds import communitydragon_asset_url
from Icons import change_profile_icon
from Riotidchanger import change_riotid


def test_profile_icon_rejects_non_positive_ids():
    with pytest.raises(ValueError, match="positive"):
        change_profile_icon(0)


def test_profile_background_asset_path_maps_to_communitydragon():
    path = "/lol-game-data/assets/ASSETS/Characters/Jhin/Skins/Skin02/Images/jhin_splash_uncentered_2.jpg"

    assert communitydragon_asset_url(path) == (
        "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/"
        "global/default/assets/characters/jhin/skins/skin02/images/"
        "jhin_splash_uncentered_2.jpg"
    )


@pytest.mark.parametrize(
    ("name", "tag", "message"),
    [
        ("", "TAG", "required"),
        ("a" * 17, "TAG", "16"),
        ("Player", "TOOLONG", "5"),
    ],
)
def test_riot_id_validation(name, tag, message):
    with pytest.raises(ValueError, match=message):
        change_riotid(name, tag)
