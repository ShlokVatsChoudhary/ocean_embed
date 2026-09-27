"""Independent validation against gridded ARGO.

Source (per the problem statement): INCOIS Live Access Server (LAS),
"Gridded ARGO". Download the NetCDF manually from the LAS web UI, then point
`load_argo` at the file.

Reference: https://las.incois.gov.in/las/
The gridded product typically provides monthly temperature/salinity on a
0.25 deg grid over the Indian Ocean. Because the exact variable names differ
between LAS exports, `load_argo` auto-detects temperature and depth.

This module never uses ARGO for training -- only for evaluation.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from . import config, harmonize


def inspect(path) -> None:
    """Print the structure of an ARGO NetCDF so you can see variable names."""
    ds = xr.open_dataset(path)
    print("dims:", dict(ds.sizes))
    print("coords:", list(ds.coords))
    print("data_vars:", list(ds.data_vars))
    for c in ("lon", "longitude", "lat", "latitude", "depth", "time"):
        if c in ds.coords:
            v = ds[c].values
            print(f"  {c}: [{np.nanmin(v)}, {np.nanmax(v)}] n={v.size}")
    ds.close()


def _find(ds, candidates):
    for c in candidates:
        if c in ds:
            return c
    return None


def _depth_name(obj) -> str | None:
    return _find(obj.coords, ["depth", "ZAX", "z", "lev", "level"])


# INCOIS ERDDAP: gridded Argo (10-day, McCreary). See the problem statement's
# "Gridded ARGO" requirement; this is the programmatic equivalent of the LAS.
ERDDAP_BASE = "https://erddap.incois.gov.in/erddap/griddap"
ERDDAP_DATASET = "incois_argo_10day_McCreary"


def download_erddap(start: str, end: str, *, fname=None,
                    lat=(5.0, 29.5), lon=(45.0, 105.0),
                    depth=(5.0, 2000.0)) -> Path:
    """Download gridded-Ango T_ANALYZED from INCOIS ERDDAP for a date range."""
    import urllib.request
    fname = fname or f"argo_{start}_{end}.nc"
    out = config.DATA_RAW / fname
    if out.exists():
        print(f"[skip] {out.name} exists")
        return out
    url = (f"{ERDDAP_BASE}/{ERDDAP_DATASET}.nc"
           f"?T_ANALYZED%5B({start}):1:({end})%5D"
           f"%5B({depth[0]}):1:({depth[1]})%5D"
           f"%5B({lat[0]}):1:({lat[1]})%5D"
           f"%5B({lon[0]}):1:({lon[1]})%5D")
    print(f"[download] ARGO {ERDDAP_DATASET}: {start} -> {end}")
    urllib.request.urlretrieve(url, out)
    print(f"[ok] {out} ({out.stat().st_size/1e6:.1f} MB)")
    return out


def regrid_to_target(da: xr.DataArray) -> xr.DataArray:
    """Regrid an ARGO field onto the project 0.25 deg grid (nearest).

    Uses explicit index lookup rather than `xarray.interp`: see the note in
    `harmonize` about `interp` returning NaN on-grid in the pinned stack.
    """
    lat = np.array(config.LAT)
    lon = np.array(config.LON)
    latname = _find(da.coords, ["latitude", "lat"])
    lonname = _find(da.coords, ["longitude", "lon"])
    dims = list(da.dims)
    order = [d for d in dims if d not in (latname, lonname)] + [latname, lonname]
    v = np.transpose(da.values, [dims.index(d) for d in order])

    iy = harmonize._nearest_axis(da[latname].values, lat)
    ix = harmonize._nearest_axis(da[lonname].values, lon)
    lead = (1,) * (v.ndim - 2)
    v = np.take_along_axis(v, iy.reshape(lead + (iy.size, 1)), axis=-2)
    v = np.take_along_axis(v, ix.reshape(lead + (1, ix.size)), axis=-1)

    out = np.transpose(v, [order.index(d) for d in dims])
    coords = {c: da[c].values for c in da.coords if c not in (latname, lonname)}
    coords[latname], coords[lonname] = lat, lon
    return xr.DataArray(out, dims=dims, coords=coords)


def load_argo(path, *, time_sel=None) -> xr.Dataset:
    """Load a gridded ARGO NetCDF and put it on the project 0.25 deg grid.

    Handles both the INCOIS ERDDAP product (variable T_ANALYZED, depth ZAX)
    and generic gridded-Argo files. Output temperature is named 'temp',
    regridded to the target lat/lon AND interpolated to the project's 15
    standard depths.

    Gaps are left as NaN. ARGO coverage is sparse by nature and this is the
    independent validation set, so no value is ever filled in.
    """
    ds = xr.open_dataset(path)
    tvar = _find(ds, ["T_ANALYZED", "temp", "temperature", "TEMP",
                      "thetao", "T"])
    if tvar is None:
        raise ValueError(f"no temperature variable found in {path}; "
                         f"available: {list(ds.data_vars)}")
    da = ds[tvar]
    if time_sel is not None:
        tname = _find(da.coords, ["time"])
        da = da.sel({tname: time_sel}, method="nearest")

    # interpolate to standard depths BEFORE horizontal regrid (cheaper)
    dz = _depth_name(da)
    if dz is not None:
        if dz != "depth":
            da = da.rename({dz: "depth"})
        da = harmonize._to_standard_depths(da)

    da = regrid_to_target(da)
    da = da.rename("temp")
    out = xr.Dataset({"temp": da})
    ds.close()
    return out


def match_to_days(argo: xr.Dataset, times: np.ndarray) -> np.ndarray:
    """Return ARGO temp aligned to the model time axis.

    Output shape (len(times), depth, lat, lon); NaN where ARGO has no data.
    """
    da = argo["temp"]
    tname = _find(da.coords, ["time"])
    if tname is None:
        # no time dim: broadcast the single field to all days
        return np.broadcast_to(da.values, (len(times), *da.shape)).copy()
    aligned = da.sel({tname: times}, method="nearest")
    return aligned.transpose(tname, ...).values


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        inspect(sys.argv[1])
