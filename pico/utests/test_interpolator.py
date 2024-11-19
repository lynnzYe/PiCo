import pytest
from pico.pneno.interpolator import *


@pytest.mark.parametrize("ioi_list, input_ioi", [
    ([0, 20, 10, 10, 20, 20], [25, 15, 15, 18, 18]),
])
def test_interpolate_bpm(ioi_list: list[float], input_ioi: list[float]):
    ifp = IFPSpeedInterpolator()
    ifp.load_ioi_list(ioi_list)
    ratio_list = []
    for e in input_ioi:
        ratio = ifp.interpolate_current_speed(e)
        ratio_list.append(ratio)
    assert ifp.is_end()
