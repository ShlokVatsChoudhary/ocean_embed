"""Harmonise multi-source satellite + reanalysis data onto one grid.

Target grid: 0.25 deg, daily, North Indian Ocean (5-30 N, 45-105 E).
Vertical: interpolate GLORYS thetao to the 15 standard depth levels.
"""
from __future__ import annotations

import numpy as np
import xarray as xr
from scipy import ndimage

from . import config

# Cells left undefined by the bilinear step are filled from the nearest valid
# cell, but only within this many target-grid cells (0.25 deg each). Anything
# farther away stays NaN and is dropped by the ocean mask, so a value can never
# be invented from a distant part of the domain.
MAX_FILL_DIST = 2.0


def target_latlon() -> tuple[np.ndarray, np.ndarray]:
    return (np.array(config.LAT, dtype="float64"),
            np.array(config.LON, dtype="float64"))


# --------------------------------------------------------------------------
# Regular-grid resampling, written out explicitly.
#
# xarray's DataArray.interp is deliberately not used anywhere in this module.
# In the pinned stack (xarray 2026.7.0 / scipy 1.18.0) it returns NaN at
# coordinates that lie exactly on the source grid, so a field can be silently
# destroyed even when the source and target grids are identical -- which is the
# case for the 0.25 deg GLORYS target. The old ffill/bfill "patching" then
# substituted whole donor columns, producing profiles that were flat (e.g.
# 27.5 C from the surface to 500 m) with errors up to 20 C.
#
# The routines below are exact-identity when the grids coincide, and the fill
# step is both distance-limited and computed per vertical level, so a deep
# level is never filled from a shallow neighbour.
# --------------------------------------------------------------------------
def _axis_weights(src: np.ndarray, tgt: np.ndarray):
    """Bracketing source indices and linear weights for each target coordinate.

    Returns (i0, i1, w, inside). When `tgt` is identical to `src` the weights
    are exactly 0 on i1, so the resampling is the identity.
    """
    src = np.asarray(src, dtype="float64")
    tgt = np.asarray(tgt, dtype="float64")
    i0 = np.clip(np.searchsorted(src, tgt, side="right") - 1, 0, src.size - 1)
    i1 = np.minimum(i0 + 1, src.size - 1)
    denom = src[i1] - src[i0]
    inside = (tgt >= src[0]) & (tgt <= src[-1])
    w = np.where(inside & (denom > 0),
                 (tgt - src[i0]) / np.where(denom > 0, denom, 1.0), 0.0)
    return i0, i1, w, inside


def _nearest_axis(src: np.ndarray, tgt: np.ndarray) -> np.ndarray:
    """Index of the nearest source coordinate for each target coordinate."""
    src = np.asarray(src, dtype="float64")
    tgt = np.asarray(tgt, dtype="float64")
    i = np.clip(np.searchsorted(src, tgt), 1, src.size - 1)
    left, right = src[i - 1], src[i]
    return np.where(np.abs(tgt - left) <= np.abs(right - tgt), i - 1, i)


def _bilinear(v: np.ndarray, src_lat, src_lon, lat, lon) -> np.ndarray:
    """Bilinear resample the last two axes of `v` from (src_lat, src_lon).

    `v` is (..., ny, nx); the result is (..., len(lat), len(lon)). A target cell
    whose bilinear stencil touches a NaN corner comes out NaN, which is the
    correct bilinear answer and is handled by `_fill_nearest` afterwards.
    """
    iy0, iy1, wy, in_y = _axis_weights(src_lat, lat)
    ix0, ix1, wx, in_x = _axis_weights(src_lon, lon)
    wy, wx = wy[:, None], wx[None, :]
    out = ((1 - wy) * (1 - wx) * v[..., iy0[:, None], ix0[None, :]]
           + (1 - wy) * wx * v[..., iy0[:, None], ix1[None, :]]
           + wy * (1 - wx) * v[..., iy1[:, None], ix0[None, :]]
           + wy * wx * v[..., iy1[:, None], ix1[None, :]])
    out[..., ~(in_y[:, None] & in_x[None, :])] = np.nan
    return out


def _fill_nearest(out: np.ndarray, valid: np.ndarray, max_dist: float) -> np.ndarray:
    """Replace NaNs in `out` with the nearest valid cell of the same level.

    `out`   : (Z, M, H, W) resampled values
    `valid` : (Z, H, W)    where a valid donor exists, collapsed over M (time)
    The index map is built once per level from data collapsed over time, so the
    fill geometry is static and cannot flicker from day to day.
    """
    if max_dist <= 0:
        return out
    z, m, h, w = out.shape
    dist, idx = ndimage.distance_transform_edt(valid, return_distances=True,
                                               return_indices=True)
    # a level with no valid cell at all has no donor: distance_transform_edt
    # reports 0 there, so it must be masked out explicitly.
    has_donor = valid.any(axis=(1, 2))
    keep = (dist <= max_dist) & has_donor[:, None, None]
    iy = np.where(keep, idx[1], 0)
    ix = np.where(keep, idx[2], 0)
    donor = np.take_along_axis(out, iy[:, None, :, :], axis=-2)
    donor = np.take_along_axis(donor, ix[:, None, :, :], axis=-1)
    filled = np.where(np.isfinite(out) | keep[:, None, :, :], out, donor)
    filled[~np.isfinite(filled)] = np.nan
    return filled


def _regrid(da: xr.DataArray, lat: np.ndarray, lon: np.ndarray, *,
            max_fill_dist: float = MAX_FILL_DIST) -> xr.DataArray:
    """Regrid the two spatial dims onto `lat`/`lon`, preserving leading dims.

    Extra leading dims (time, depth) are kept. Cells the bilinear step leaves
    undefined -- coastal cells whose stencil touches land, and target cells
    just outside the source domain -- are filled from the nearest valid cell of
    the same vertical level within `max_fill_dist`; anything farther stays NaN
    for the ocean mask in `build_arrays` to drop.
    """
    src_lat = np.asarray(da["latitude"].values, dtype="float64")
    src_lon = np.asarray(da["longitude"].values, dtype="float64")
    lat = np.asarray(lat, dtype="float64")
    lon = np.asarray(lon, dtype="float64")

    orig = list(da.dims)
    lead = [d for d in orig if d not in ("latitude", "longitude")]
    perm = lead + ["latitude", "longitude"]
    inv = [perm.index(d) for d in orig]
    has_z = "depth" in lead
    rest = [d for d in lead if d != "depth"]

    v = np.transpose(da.values, [orig.index(d) for d in perm]).astype("float64")
    v = np.moveaxis(v, lead.index("depth"), 0) if has_z else v[None]
    rest_shape = [da.sizes[d] for d in rest]
    v = v.reshape(v.shape[0], -1, v.shape[-2], v.shape[-1])          # (Z, M, H, W)

    if (src_lat.shape == lat.shape and np.array_equal(src_lat, lat)
            and np.array_equal(src_lon, lon)):
        out = v.copy()                       # grids identical: exact identity
    else:
        out = _bilinear(v, src_lat, src_lon, lat, lon)
    out = _fill_nearest(out, np.isfinite(out).any(1), max_fill_dist)

    out = out.reshape([out.shape[0]] + rest_shape + list(out.shape[-2:]))
    if has_z:
        out = np.moveaxis(out, 0, lead.index("depth"))
    else:
        out = out[0]
    out = np.transpose(out, inv)
    coords = {d: da[d].values for d in orig
              if d in da.coords and d not in ("latitude", "longitude")}
    coords["latitude"], coords["longitude"] = lat, lon
    return xr.DataArray(out, dims=orig, coords=coords)


def _regrid_nearest(da: xr.DataArray, lat: np.ndarray, lon: np.ndarray) -> xr.DataArray:
    """Nearest-neighbour regrid of a 2-D (latitude, longitude) field."""
    lat = np.asarray(lat, dtype="float64")
    lon = np.asarray(lon, dtype="float64")
    iy = _nearest_axis(da["latitude"].values, lat)
    ix = _nearest_axis(da["longitude"].values, lon)
    v = da.values[np.ix_(iy, ix)]
    return xr.DataArray(v, dims=("latitude", "longitude"),
                        coords={"latitude": lat, "longitude": lon})


def _ocean_mask(G: xr.Dataset, lat: np.ndarray, lon: np.ndarray,
                var: str = "thetao") -> xr.DataArray:
    """Static land/ocean mask from the target: a cell is ocean if `var` is
    finite there on the shallowest level for at least one day.

    Returned with the same 0.25 deg target coords as the value arrays.
    """
    valid = np.isfinite(G[var].isel(depth=0)).any("time").astype("float32")
    m = _regrid_nearest(valid, lat, lon)
    m = (m.values > 0.5)
    return xr.DataArray(m, dims=("latitude", "longitude"),
                        coords={"latitude": lat, "longitude": lon})


def _seabed_depth(G: xr.Dataset, var: str, lat: np.ndarray,
                  lon: np.ndarray) -> xr.DataArray:
    """Per-cell seabed depth from the deepest native level holding data.

    GLORYS masks cells below the seabed as NaN, so the deepest finite native
    level is a good bathymetry estimate. It slightly *over*estimates the true
    seabed (by up to one level spacing), so it is a safety net rather than an
    exact floor: the vertical interpolation is what actually keeps
    below-seabed levels NaN.
    """
    da = G[var]
    d = np.asarray(da["depth"].values, dtype="float64")
    valid = np.isfinite(da).any("time").values          # (Z, H, W)
    has = valid.any(axis=0)
    last = valid.shape[0] - 1 - np.argmax(valid[::-1], axis=0)
    seabed = np.where(has, d[last], np.nan)
    sda = xr.DataArray(seabed, dims=("latitude", "longitude"),
                       coords={"latitude": da["latitude"].values,
                               "longitude": da["longitude"].values})
    return _regrid_nearest(sda, lat, lon)


def _to_standard_depths(da: xr.DataArray, depths=config.DEPTHS) -> xr.DataArray:
    """Linear vertical interpolation to the standard depths.

    Only the surface level is extrapolated: GLORYS' shallowest level is
    ~0.49 m, so 0 m takes the shallowest native value. Deeper gaps -- levels
    below the sea floor, where the reanalysis is NaN -- are left as NaN and
    dropped by the bathymetry mask in `build_arrays`. They are deliberately not
    filled downwards, which used to smear warm surface water to 1000 m over
    shelves and is the other half of the flat-profile artefact.
    """
    d = np.asarray(da["depth"].values, dtype="float64")
    tgt = np.asarray(list(depths), dtype="float64")
    dims = list(da.dims)
    v = da.transpose(..., "depth").values.astype("float64")
    i0, i1, w, inside = _axis_weights(d, tgt)
    out = (1 - w) * v[..., i0] + w * v[..., i1]
    out[..., ~inside] = np.nan
    out[..., 0] = np.where(inside[0], out[..., 0], v[..., i0[0]])
    # indexing the depth axis moved it last; put it back where it was
    z = dims.index("depth")
    out = np.moveaxis(out, -1, z)
    coords = {c: da[c].values for c in da.coords if c != "depth"}
    coords["depth"] = tgt
    return xr.DataArray(out, dims=dims, coords=coords)


def build_arrays(target_path, duacs_path, ostia_path, *, sss_path=None,
                 target_var: str = "thetao_glor",
                 save: bool = True, tag: str = "demo") -> dict:
    """Build aligned X (surface inputs) and Y (temperature profiles).

    Returns a dict with X, Y, channel names, and the target lat/lon/depth.
    X shape: (time, channel, lat, lon)
    Y shape: (time, depth, lat, lon)

    `sss_path` is optional: when given, sea-surface salinity is regridded and
    added as a channel (5 surface inputs instead of 4).
    """
    lat, lon = target_latlon()

    G = xr.open_dataset(target_path)
    D = xr.open_dataset(duacs_path)
    O = xr.open_dataset(ostia_path)
    S = xr.open_dataset(sss_path) if sss_path is not None else None

    # ---- TARGET: subsurface temperature at standard depths ----
    theta = _to_standard_depths(G[target_var])
    theta = _regrid(theta, lat, lon)

    # ---- bathymetry: drop target depths that lie below the seabed ----
    # Belt-and-braces with the NaN-preserving vertical interpolation: the mask
    # also catches cells where the estimated seabed is shallower than the last
    # level the reanalysis actually reported.
    seabed = _seabed_depth(G, target_var, lat, lon)
    theta = theta.where(theta["depth"] <= seabed)

    # ---- INPUT surface channels, in `config.INPUT_CHANNELS` order ----
    chans: dict[str, xr.DataArray] = {}
    chans["sst"] = _regrid(O["analysed_sst"] - 273.15, lat, lon)   # K -> C
    if S is not None:
        sv = next((c for c in ("sos", "sss", "SOS", "SSS") if c in S), None)
        if sv is not None:
            sda = S[sv]
            # the SMAP+SMOS L4 product carries a singleton depth dimension
            for d in ("depth", "lev", "level", "z"):
                if d in sda.dims:
                    sda = sda.isel({d: 0}, drop=True)
                    break
            chans["sss"] = _regrid(sda, lat, lon)
    chans["sla"] = _regrid(D["sla"], lat, lon)
    chans["ugos"] = _regrid(D["ugos"], lat, lon)
    chans["vgos"] = _regrid(D["vgos"], lat, lon)
    # Fallback surface salinity / currents carried inside the target file
    # (GLORYS12V1 has so/uo/vo; the 0.25 ensemble has so_glor/uo_glor/vo_glor).
    # Only used when a real SSS product was not supplied, to avoid ambiguity.
    if "sss" not in chans:
        for ch, cands in {"sss": ["so_glor", "so"],
                          "uo": ["uo_glor", "uo"],
                          "vo": ["vo_glor", "vo"]}.items():
            vname = next((c for c in cands if c in G), None)
            if vname is not None:
                chans[ch] = _regrid(G[vname].isel(depth=0), lat, lon)

    # Align on common times (must include every channel actually present)
    common_time = theta["time"].values
    for v in chans.values():
        common_time = np.intersect1d(common_time, v["time"].values)
    theta = theta.sel(time=common_time)
    chans = {k: v.sel(time=common_time) for k, v in chans.items()}

    # ---- remove land: GLORYS defines ocean, applied consistently to all ----
    mask = _ocean_mask(G, lat, lon, var=target_var)
    theta = theta.where(mask)
    chans = {k: v.where(mask) for k, v in chans.items()}

    names = list(chans.keys())
    X = np.stack([chans[n].transpose("time", "latitude", "longitude").values
                  for n in names], axis=1).astype("float32")           # (T,C,H,W)
    Y = theta.transpose("time", "depth", "latitude", "longitude"
                        ).values.astype("float32")                     # (T,Z,H,W)

    out = dict(X=X, Y=Y, channels=names, lat=lat, lon=lon,
               depths=list(config.DEPTHS), time=common_time,
               seabed=seabed.values)

    if save:
        np.save(config.DATA_PROC / f"bathy_{tag}.npy", seabed.values.astype("float32"))
        xp = config.DATA_PROC / f"X_{tag}.npy"
        yp = config.DATA_PROC / f"Y_{tag}.npy"
        np.save(xp, X)
        np.save(yp, Y)
        stats = {}
        for i, n in enumerate(names):
            xi = X[:, i]
            stats[f"x_mean_{n}"] = float(np.nanmean(xi))
            stats[f"x_std_{n}"] = float(np.nanstd(xi))
            print(f"  {n:5s} mean={stats[f'x_mean_{n}']:10.4f}  "
                  f"std={stats[f'x_std_{n}']:9.4f}")
        stats["y_mean"] = float(np.nanmean(Y))
        stats["y_std"] = float(np.nanstd(Y))
        np.savez(config.DATA_PROC / f"stats_{tag}.npz", **stats)
        np.save(config.DATA_PROC / f"channels_{tag}.npy", np.array(names))
        out["paths"] = {"X": xp, "Y": yp}

    if S is not None:
        S.close()
    G.close()
    D.close()
    O.close()
    return out
