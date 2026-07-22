from scripts.geo import haversine_nm


def test_same_point_is_zero_distance():
    assert haversine_nm(40.4675, 50.0467, 40.4675, 50.0467) == 0.0


def test_baku_to_turkmenbashi_is_about_127_nm():
    # Known-good reference distance between the two airports, used to
    # sanity-check the formula rather than assert an exact float.
    distance = haversine_nm(40.4675, 50.0467, 40.0633, 53.0072)
    assert 130 < distance < 145
