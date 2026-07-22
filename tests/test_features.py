import pytest

from Icons import change_profile_icon
from Riotidchanger import change_riotid


def test_profile_icon_rejects_non_positive_ids():
    with pytest.raises(ValueError, match="positivo"):
        change_profile_icon(0)


@pytest.mark.parametrize(
    ("name", "tag", "message"),
    [
        ("", "TAG", "obligatorios"),
        ("a" * 17, "TAG", "16"),
        ("Player", "TOOLONG", "5"),
    ],
)
def test_riot_id_validation(name, tag, message):
    with pytest.raises(ValueError, match=message):
        change_riotid(name, tag)
