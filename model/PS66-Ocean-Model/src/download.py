"""Thin, verified wrapper around `copernicusmarine.subset` (v2 API).

Each function downloads one dataset for the North Indian Ocean box and a
date range, writing a NetCDF into ``data/raw``.
"""
from __future__ import annotations

from pathlib import Path

import copernicusmarine

from . import config


def _subset(key: str, start: str, end: str, *, depth: bool = False,
            extra_vars: list[str] | None = None, overwrite: bool = False) -> Path:
    """Download one configured dataset for the NIO box and date range.

    Parameters
    ----------
    key : one of "glorys", "duacs", "ostia"
    start, end : ISO dates, e.g. "2020-01-01"
    depth : whether to send depth bounds (only GLORYS supports it)
    extra_vars : override the configured variable list
    """
    meta = config.DATASETS[key]
    variables = extra_vars or meta["variables"]
    max_depth = float(meta.get("max_depth", 1000.0))
    fname = meta["filename"].format(start=start, end=end)
    # Version the filename by the depth cap so changing max_depth forces a fresh
    # download instead of silently reusing a shallower file.
    if depth and meta.get("has_depth"):
        stem, ext = fname.rsplit(".", 1)
        fname = f"{stem}_z{int(max_depth)}.{ext}"
    out = config.DATA_RAW / fname
    if out.exists() and not overwrite:
        print(f"[skip] {out.name} already exists")
        return out

    kwargs = dict(
        dataset_id=meta["dataset_id"],
        variables=variables,
        minimum_longitude=config.LON_MIN,
        maximum_longitude=config.LON_MAX,
        minimum_latitude=config.LAT_MIN,
        maximum_latitude=config.LAT_MAX,
        start_datetime=start,
        end_datetime=end,
        output_filename=fname,
        output_directory=str(config.DATA_RAW),
        overwrite=overwrite,
        disable_progress_bar=False,
    )
    # GLORYS is a full-depth product: keep surface down to 1000 m so we can
    # build the standard-depth targets.
    if depth and meta["has_depth"]:
        kwargs["minimum_depth"] = 0.0
        kwargs["maximum_depth"] = max_depth

    print(f"[download] {key}: {meta['dataset_id']}")
    print(f"           vars={variables}  {start} -> {end}")
    copernicusmarine.subset(**kwargs)
    if not out.exists():
        raise FileNotFoundError(f"expected output missing: {out}")
    print(f"[ok] {out}")
    return out


def download_target(start: str, end: str, *, overwrite: bool = False) -> Path:
    """Download the temperature target (0.25 deg GLORYS ensemble member)."""
    return _subset("target", start, end, depth=True, overwrite=overwrite)


def download_glorys(start: str, end: str, *, overwrite: bool = False) -> Path:
    return _subset("glorys", start, end, depth=True, overwrite=overwrite)


def download_duacs(start: str, end: str, *, overwrite: bool = False) -> Path:
    return _subset("duacs", start, end, overwrite=overwrite)


def download_ostia(start: str, end: str, *, overwrite: bool = False) -> Path:
    return _subset("ostia", start, end, overwrite=overwrite)


def download_sss(start: str, end: str, *, overwrite: bool = False) -> Path:
    """Sea-surface salinity (SMAP+SMOS multi-observation L4, 0.125 deg daily)."""
    return _subset("sss", start, end, overwrite=overwrite)


def _fetch(url: str, dest: Path, *, overwrite: bool = False) -> Path:
    """HTTP download with resume; skips if a complete file already exists."""
    import urllib.request

    if dest.exists() and not overwrite and dest.stat().st_size > 0:
        print(f"[skip] {dest.name} already exists")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "siH-ps66/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    tmp.replace(dest)
    return dest


def download_ccmp_day(date: str, *, overwrite: bool = False) -> Path:
    """Download one day of CCMP v3.1 winds (published daily by RSS)."""
    import datetime as _dt

    y, m, d = (int(x) for x in date.split("-"))
    ymd = f"{y}{m:02d}{d:02d}"
    url = config.CCMP["url"].format(base=config.CCMP["base_url"], year=y,
                                     month=m, ymd=ymd)
    dest = config.CCMP_RAW / f"CCMP_{ymd}.nc"
    return _fetch(url, dest, overwrite=overwrite)


def download_ccmp(start: str, end: str, *, overwrite: bool = False) -> list[Path]:
    """Download CCMP winds for every day in [start, end]."""
    import datetime as _dt

    d0 = _dt.date.fromisoformat(start)
    d1 = _dt.date.fromisoformat(end)
    out = []
    day = d0
    while day <= d1:
        out.append(download_ccmp_day(day.isoformat(), overwrite=overwrite))
        day += _dt.timedelta(days=1)
    return out


def download_all(start: str, end: str, *, overwrite: bool = False) -> dict[str, Path]:
    """Download the datasets needed for the pipeline."""
    return {
        "target": download_target(start, end, overwrite=overwrite),
        "duacs": download_duacs(start, end, overwrite=overwrite),
        "ostia": download_ostia(start, end, overwrite=overwrite),
        "sss": download_sss(start, end, overwrite=overwrite),
    }
