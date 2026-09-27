"""Regression tests for the regridding in `src.harmonize`.

These pin the exact failure that corrupted the training data: xarray's
`DataArray.interp` returned NaN at coordinates lying exactly on the source
grid, and the old unconditional `ffill`/`bfill` then substituted whole donor
columns. A known ocean cell that should be 28.08 C at the surface and 9.86 C
at 500 m came out as 27.5 C flat from the surface to 500 m.

Run standalone (`python tests/test_harmonize.py`) or under pytest. No data
downloads: everything here is synthetic.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, harmonize  # noqa: E402

TGT_LAT = np.array(config.LAT)
TGT_LON = np.array(config.LON)
H, W = TGT_LAT.size, TGT_LON.size


def _da(v, lat, lon, dims=("latitude", "longitude")):
    coords = {}
    if "latitude" in dims:
        coords["latitude"] = lat
    if "longitude" in dims:
        coords["longitude"] = lon
    return xr.DataArray(v, dims=dims, coords=coords)


def _field(v, depths):
    """(T, Z, H, W) -> DataArray on the project grid."""
    v = np.asarray(v, dtype="float64")
    return xr.DataArray(
        v,
        dims=("time", "depth", "latitude", "longitude"),
        coords={"time": np.arange(v.shape[0]),
                "depth": np.asarray(depths, dtype="float64"),
                "latitude": TGT_LAT, "longitude": TGT_LON},
    )


def _profile(v, depths):
    """(Z,) or (Z, H, W) -> (time=1, Z, H, W) DataArray on the project grid."""
    v = np.asarray(v, dtype="float64")
    if v.ndim == 1:
        v = np.broadcast_to(v[:, None, None], (v.size, H, W))
    return _field(v[None], depths)


# --------------------------------------------------------------------------
# the regression itself
# --------------------------------------------------------------------------
def test_regrid_is_identity_when_grids_match():
    """Regridding a field already on the target grid must change nothing.

    This is the case for the 0.25 deg GLORYS target, and it is where the old
    implementation destroyed the data.
    """
    rng = np.random.default_rng(0)
    v = rng.normal(20.0, 3.0, size=(H, W))
    v[10:14, 20:26] = np.nan          # a "land" block, to exercise the fill

    out = harmonize._regrid(_da(v, TGT_LAT, TGT_LON), TGT_LAT, TGT_LON,
                            max_fill_dist=0.0).values

    assert out.shape == v.shape
    assert np.array_equal(np.isnan(out), np.isnan(v)), "NaN pattern changed"
    assert np.allclose(out[~np.isnan(out)], v[~np.isnan(v)], rtol=0, atol=1e-9), \
        "values on matching grids were altered"


def test_regrid_preserves_dims_and_shape():
    v = np.zeros((3, 4, H, W))
    v[:] = np.arange(H)[None, None, :, None]
    da = _field(v, [10.0, 50.0, 100.0, 200.0])

    out = harmonize._regrid(da, TGT_LAT, TGT_LON, max_fill_dist=0.0)

    assert out.dims == da.dims
    assert out.shape == da.shape
    # build_arrays indexes on these, so they must survive the regrid
    assert np.allclose(out["depth"].values, [10.0, 50.0, 100.0, 200.0])
    assert np.allclose(out["time"].values, [0, 1, 2])
    assert np.allclose(out.transpose("time", "depth", "latitude",
                                     "longitude").values, v)


def test_regrid_preserves_leading_dim_order_when_depth_is_not_last():
    """A (depth, time, lat, lon) source must come back in the same order."""
    v = np.zeros((2, 3, H, W))
    da = xr.DataArray(
        v,
        dims=("depth", "time", "latitude", "longitude"),
        coords={"depth": [10.0, 500.0], "time": np.arange(3),
                "latitude": TGT_LAT, "longitude": TGT_LON},
    )
    out = harmonize._regrid(da, TGT_LAT, TGT_LON, max_fill_dist=0.0)
    assert out.dims == da.dims
    assert out.shape == (2, 3, H, W)


# --------------------------------------------------------------------------
# bilinear correctness on a genuinely offset source grid
# --------------------------------------------------------------------------
def test_bilinear_matches_hand_computed_value():
    """A 0.125 deg source resampled onto the target, checked against arithmetic."""
    src_lat = np.arange(45.0, 50.0 + 1e-9, 0.125)
    src_lon = np.arange(45.0, 50.0 + 1e-9, 0.125)
    ramp = src_lat[:, None] * 2.0 + src_lon[None, :] * 3.0

    out = harmonize._regrid(_da(ramp, src_lat, src_lon), TGT_LAT, TGT_LON,
                            max_fill_dist=0.0).values

    sub_lat = TGT_LAT[(TGT_LAT >= src_lat[0]) & (TGT_LAT <= src_lat[-1])]
    sub_lon = TGT_LON[(TGT_LON >= src_lon[0]) & (TGT_LON <= src_lon[-1])]
    expect = sub_lat[:, None] * 2.0 + sub_lon[None, :] * 3.0
    got = out[np.ix_(np.searchsorted(TGT_LAT, sub_lat),
                     np.searchsorted(TGT_LON, sub_lon))]
    assert np.allclose(got, expect, atol=1e-9), "bilinear is not exact on a ramp"


def test_out_of_domain_target_stays_nan_without_fill():
    """DUACS starts at 5.0625 N, so the 5.00 N row is outside the source."""
    src_lat = np.arange(5.0625, 30.0, 0.125)
    src_lon = np.arange(45.0, 105.0, 0.125)
    v = np.full((src_lat.size, src_lon.size), 1.0)

    out = harmonize._regrid(_da(v, src_lat, src_lon), TGT_LAT, TGT_LON,
                            max_fill_dist=0.0).values

    assert np.isnan(out[0]).all(), "out-of-domain row was silently extrapolated"
    # every row strictly inside the source domain, every column the source spans
    assert np.isfinite(out[1:-1, :-1]).all()
    assert np.isnan(out[-1]).all(), "out-of-domain column was silently extrapolated"


# --------------------------------------------------------------------------
# the fill must be local and level-aware
# --------------------------------------------------------------------------
def test_fill_respects_max_distance():
    """A NaN region wider than the fill radius must stay NaN."""
    src_lat = np.arange(5.0, 30.0 + 1e-9, 0.25)
    src_lon = np.arange(45.0, 105.0 + 1e-9, 0.25)
    v = np.full((src_lat.size, src_lon.size), 5.0)
    v[10:20, 10:30] = np.nan                     # a 10x20 cell hole

    out = harmonize._regrid(_da(v, src_lat, src_lon), TGT_LAT, TGT_LON,
                            max_fill_dist=2.0).values
    assert np.isfinite(out[9, 10:30]).all(), "near rim should be filled"
    assert np.isnan(out[10:20, 10:30]).all(), \
        "a hole deeper than max_fill_dist must not be invented"


def test_fill_does_not_cross_vertical_levels():
    """A deep level must never be filled from a valid shallow level.

    This is the property whose absence produced flat 27.5 C profiles.
    """
    v = np.full((2, 2, H, W), 3.0)                # (time, depth, lat, lon)
    v[:, 1, 30:40, 30:40] = np.nan               # deep level has a hole
    out = harmonize._regrid(_field(v, [10.0, 500.0]), TGT_LAT, TGT_LON,
                            max_fill_dist=2.0).values

    assert np.isfinite(out[0, 1, 29, 30:40]).all(), "rim of the hole should fill"
    assert np.isnan(out[0, 1, 30:40, 30:40]).all(), \
        "deep level was filled from the shallow level's values"
    assert np.isfinite(out[0, 0, 30:40, 30:40]).all(), "shallow level untouched"


def test_fill_footprint_is_static_in_time():
    """The set of cells left unfilled must not change from day to day.

    The donor map is built from data collapsed over time, so a cell that is
    missing on some days but present on others cannot grow or shrink the
    filled region as the source oscillates in and out.
    """
    v = np.zeros((3, 1, H, W))
    v[0, 0, 20, 20:24] = np.nan          # a gap on day 0 only ...
    v[2, 0, 20, 20:24] = np.nan          # ... and again, offset, on day 2
    v[:, 0, 20, 20:24] = np.where(
        np.isfinite(v[:, 0, 20, 20:24]).all(0, keepdims=True), 0.0, np.nan)
    # make the whole block invalid on at least one day, so it is never a donor
    v[1, 0, 20, 20:24] = np.nan

    out = harmonize._regrid(_field(v, [10.0]), TGT_LAT, TGT_LON,
                            max_fill_dist=2.0).values
    foot = np.isnan(out[:, 0])
    assert np.array_equal(foot[0], foot[1]) and np.array_equal(foot[1], foot[2]), \
        "the unfilled region changed between days"
    assert not foot[0, 19, 20:24].any(), "the rim should have been filled"


def test_level_with_no_data_anywhere_stays_nan():
    v = np.full((1, 1, H, W), np.nan)
    out = harmonize._regrid(_field(v, [10.0]), TGT_LAT, TGT_LON,
                            max_fill_dist=2.0).values
    assert np.isnan(out).all(), "an all-NaN level must not borrow a donor"


def test_fill_never_produces_nonfinite():
    """Whatever the input, the output may only contain finite values or NaN."""
    rng = np.random.default_rng(7)
    v = rng.normal(size=(3, 2, H, W))
    v[rng.random(v.shape) < 0.3] = np.nan
    out = harmonize._regrid(_field(v, [10.0, 500.0]), TGT_LAT, TGT_LON).values
    assert not np.isinf(out).any(), "fill produced infinities"


# --------------------------------------------------------------------------
# vertical interpolation
# --------------------------------------------------------------------------
def test_to_standard_depths_interpolates_linearly():
    out = harmonize._to_standard_depths(
        _profile([30.0, 20.0], [0.0, 1000.0])).values[0, :, 0, 0]
    for zi, z in enumerate(config.DEPTHS):
        assert abs(out[zi] - (30.0 - 10.0 * z / 1000.0)) < 1e-9, \
            f"{z} m: got {out[zi]}"


def test_to_standard_depths_extrapolates_only_the_surface():
    """GLORYS' shallowest level is ~0.49 m, so 0 m takes the native surface."""
    out = harmonize._to_standard_depths(
        _profile([28.0, 9.0], [0.5058, 628.0])).values[0, :, 0, 0]
    assert out[0] == 28.0, "0 m should take the shallowest native value"
    inside = [z for z in config.DEPTHS if z <= 628.0]
    assert np.isfinite(out[:len(inside)]).all(), "levels inside the profile were lost"
    assert np.isnan(out[len(inside):]).all(), \
        "levels below the seabed should stay NaN"


def test_to_standard_depths_does_not_fill_below_the_seabed():
    """Below-seabed levels must stay NaN, not inherit the deepest warm value.

    The old ffill/bfill produced 27.5 C all the way to 500 m in cells whose
    seabed was far shallower.
    """
    out = harmonize._to_standard_depths(
        _profile([28.0, 27.0, 20.0, np.nan], [0.5, 50.0, 100.0, 200.0])
    ).values[0, :, 0, 0]
    assert np.isnan(out[-1]), "the deepest level was filled instead of left NaN"
    assert out[0] > 27.0 and out[1] > 26.0, "valid levels were damaged"


def test_to_standard_depths_returns_target_depth_coord():
    da = _profile([28.0, 9.0], [0.5058, 628.0])
    out = harmonize._to_standard_depths(da)
    assert out.dims == da.dims
    assert np.allclose(out["depth"].values, config.DEPTHS)
    assert "time" in out.coords, "build_arrays selects on time after this"


# --------------------------------------------------------------------------
# nearest-neighbour path (ocean mask, bathymetry)
# --------------------------------------------------------------------------
def test_regrid_nearest_is_identity_when_grids_match():
    rng = np.random.default_rng(1)
    v = rng.integers(0, 2, size=(H, W)).astype("float64")
    out = harmonize._regrid_nearest(_da(v, TGT_LAT, TGT_LON), TGT_LAT, TGT_LON)
    assert np.array_equal(out.values, v)


def test_regrid_nearest_picks_the_closest_source_cell():
    src_lat = np.array([5.0625, 5.1875, 5.3125])
    src_lon = np.array([45.0, 45.125, 45.25])
    v = np.arange(1.0, 10.0).reshape(3, 3)
    out = harmonize._regrid_nearest(_da(v, src_lat, src_lon),
                                    np.array([5.0, 5.06, 5.13, 5.2]),
                                    np.array([45.0, 45.06, 45.13, 45.2]))
    # rows 0,0,1,1 and cols 0,0,1,2 of [[1,2,3],[4,5,6],[7,8,9]]
    assert out.values.tolist() == [[1.0, 1.0, 2.0, 3.0],
                                   [1.0, 1.0, 2.0, 3.0],
                                   [4.0, 4.0, 5.0, 6.0],
                                   [4.0, 4.0, 5.0, 6.0]]


# --------------------------------------------------------------------------
def main() -> int:
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {name}\n      {exc}")
        except Exception as exc:                      # noqa: BLE001
            failed += 1
            print(f"ERROR {name}\n      {type(exc).__name__}: {exc}")
        else:
            print(f"ok    {name}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
