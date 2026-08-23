from src.core_estimation import EXPOSURE
from src.heterogeneity_inference import slope_weights, subtract_weights


def test_peak_difference_reduces_to_interaction_coefficient():
    slopes = slope_weights("peak")
    difference = subtract_weights(slopes["peak"], slopes["off_peak"])
    assert difference == {f"{EXPOSURE}_x_peak": 1.0}


def test_region_difference_has_opposite_unit_weights():
    slopes = slope_weights("region")
    difference = subtract_weights(slopes["NSW1"], slopes["VIC1"])
    assert difference[f"{EXPOSURE}_x_NSW1"] == 1.0
    assert difference[f"{EXPOSURE}_x_VIC1"] == -1.0
