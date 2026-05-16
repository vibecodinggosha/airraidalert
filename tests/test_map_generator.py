import pytest
from map_generator import (
    _to_svg_xy,
    _marker_color,
    _build_markers,
    REGION_CAPITALS,
    API_TO_ID,
    _WEAPON_COLORS,
)


# Calibration tolerance in pixels
_TOL = 40


def test_kyiv_coordinates():
    x, y = _to_svg_xy(50.450, 30.523)
    assert 460 < x < 540, f"Kyiv x={x:.0f} out of range"
    assert 170 < y < 240, f"Kyiv y={y:.0f} out of range"


def test_kharkiv_coordinates():
    x, y = _to_svg_xy(49.993, 36.230)
    assert 700 < x < 780, f"Kharkiv x={x:.0f} out of range"
    assert 190 < y < 250, f"Kharkiv y={y:.0f} out of range"


def test_odesa_coordinates():
    x, y = _to_svg_xy(46.482, 30.723)
    assert 465 < x < 535, f"Odesa x={x:.0f} out of range"
    assert 390 < y < 455, f"Odesa y={y:.0f} out of range"


def test_lviv_west_of_kyiv():
    x_lviv, _ = _to_svg_xy(49.839, 24.029)
    x_kyiv, _ = _to_svg_xy(50.450, 30.523)
    assert x_lviv < x_kyiv, "Lviv should be west (smaller x) of Kyiv"


def test_kharkiv_east_of_kyiv():
    x_kharkiv, _ = _to_svg_xy(49.993, 36.230)
    x_kyiv, _ = _to_svg_xy(50.450, 30.523)
    assert x_kharkiv > x_kyiv, "Kharkiv should be east (larger x) of Kyiv"


def test_odesa_south_of_kyiv():
    _, y_odesa = _to_svg_xy(46.482, 30.723)
    _, y_kyiv = _to_svg_xy(50.450, 30.523)
    assert y_odesa > y_kyiv, "Odesa should be south (larger y) of Kyiv"


def test_all_regions_have_capitals():
    for region in API_TO_ID:
        assert region in REGION_CAPITALS, f"Missing capital for {region!r}"


def test_all_capitals_in_ukraine_bounds():
    for region, (lat, lng) in REGION_CAPITALS.items():
        assert 44.0 <= lat <= 53.0, f"{region}: lat {lat} out of Ukraine bounds"
        assert 22.0 <= lng <= 41.0, f"{region}: lng {lng} out of Ukraine bounds"
        x, y = _to_svg_xy(lat, lng)
        assert 0 < x < 1100, f"{region}: x={x:.0f} off canvas"
        assert 0 < y < 800, f"{region}: y={y:.0f} off canvas"


def test_marker_color_drone():
    color = _marker_color({"strike_means": ["шахед", "дрон бпла"]})
    assert color == "#e67e22"


def test_marker_color_missile():
    color = _marker_color({"strike_means": ["крилата ракета х-101"]})
    assert color == "#e74c3c"


def test_marker_color_ballistic():
    color = _marker_color({"strike_means": ["балістична ракета"]})
    assert color == "#8e44ad"


def test_marker_color_default():
    assert _marker_color(None) == "#e74c3c"
    assert _marker_color({}) == "#e74c3c"
    assert _marker_color({"strike_means": []}) == "#e74c3c"


def test_build_markers_svg_valid():
    svg = _build_markers(["Київська область", "Харківська область"], "#ff0000")
    assert "<circle" in svg
    assert svg.count("<circle") == 6  # 3 rings × 2 regions


def test_build_markers_empty():
    svg = _build_markers([], "#ff0000")
    assert svg == ""


def test_build_markers_unknown_region():
    svg = _build_markers(["Невідома область"], "#ff0000")
    assert "<circle" not in svg
