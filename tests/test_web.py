from web import server


def test_profile_api_is_registered_before_spa_catch_all():
    route_paths = [route.path for route in server.app.routes]

    assert route_paths.index("/api/profile") < route_paths.index("/{path:path}")


def test_regalia_assets_use_selected_prestige_crest_and_ranked_banner():
    assets = server.build_regalia_assets({
        "crestType": "prestige",
        "selectedPrestigeCrest": 19,
        "summonerLevel": 857,
        "bannerType": "lastSeasonHighestRank",
        "lastSeasonHighestRank": "GOLD",
    })

    assert assets["crestUrl"].endswith("prestige_crest_lvl_450.png")
    assert assets["bannerUrl"].endswith("bannerskins/gold.png")
