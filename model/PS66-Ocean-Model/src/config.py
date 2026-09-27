"""Central configuration for the PS66 subsurface-temperature project.

All dataset IDs were verified against the Copernicus Marine catalogue
(`copernicusmarine describe`) on this machine.
"""
from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROC = ROOT / "data" / "processed"
FIGURES = ROOT / "figures"
CHECKPOINTS = ROOT / "checkpoints"
for _p in (DATA_RAW, DATA_PROC, FIGURES, CHECKPOINTS):
    _p.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Domain: North Indian Ocean
# --------------------------------------------------------------------------
LON_MIN, LON_MAX = 45.0, 105.0
LAT_MIN, LAT_MAX = 5.0, 30.0
RES = 0.25  # degrees

# Target 0.25 deg grid (regular lat/lon)
LON = [LON_MIN + RES * i for i in range(round((LON_MAX - LON_MIN) / RES) + 1)]
LAT = [LAT_MIN + RES * i for i in range(round((LAT_MAX - LAT_MIN) / RES) + 1)]

# Standard depth levels (metres) we reconstruct
DEPTHS = [0, 5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 300, 500, 700, 1000]

# --------------------------------------------------------------------------
# Copernicus Marine datasets (verified IDs)
# --------------------------------------------------------------------------
DATASETS = {
    # ---- TARGET: GLORYS ensemble @ 0.25 deg (daily, 75 levels, 1993-2024) ----
    # `thetao_glor` is the GLORYS member. Native 0.25 deg -> no regrid needed.
    # Chosen over GLORYS12V1 (0.083 deg) for a ~13x smaller/faster download.
    "target": {
        "dataset_id": "cmems_mod_glo_phy-all_my_0.25deg_P1D-m",
        "variables": ["thetao_glor"],
        "has_depth": True,
        "max_depth": 1500.0,   # fetch below 1000 m so the 1000 m level is interpolated
        "filename": "target_{start}_{end}.nc",
    },
    # Fallback target: full GLORYS12V1 reanalysis at 0.083 deg (heavier).
    "glorys": {
        "dataset_id": "cmems_mod_glo_phy_my_0.083deg_P1D-m",
        "variables": ["thetao", "so", "uo", "vo", "zos"],
        "has_depth": True,
        "max_depth": 1500.0,
        "filename": "glorys_{start}_{end}.nc",
    },
    # ---- SSH / SLA: DUACS L4 (0.125 deg, daily, multiyear) ----
    "duacs": {
        "dataset_id": "cmems_obs-sl_glo_phy-ssh_my_allsat-l4-duacs-0.125deg_P1D",
        "variables": ["sla", "adt", "ugos", "vgos"],
        "has_depth": False,
        "filename": "duacs_{start}_{end}.nc",
    },
    # ---- SST: OSTIA L4 reprocessed (0.05 deg, daily) ----
    "ostia": {
        "dataset_id": "METOFFICE-GLO-SST-L4-REP-OBS-SST",
        "variables": ["analysed_sst"],
        "has_depth": False,
        "filename": "ostia_{start}_{end}.nc",
        # OSTIA is delivered in Kelvin
        "kelvin_to_celsius": True,
    },
    # ---- SSS: multi-observation SMAP+SMOS L4 (0.125 deg, daily) ----
    # PS66 DOI 10.48670/moi-00051. Variable is `sos` (sea_surface_salinity),
    # NOT `sss`. Units are PSU.
    "sss": {
        "dataset_id": "cmems_obs-mob_glo_phy-sss_my_multi_P1D",
        "variables": ["sos"],
        "has_depth": False,
        "filename": "sss_{start}_{end}.nc",
    },
}

# --------------------------------------------------------------------------
# CCMP v3.1 winds (Remote Sensing Systems) -- public HTTP, no login.
# Daily global L4 files, one per day, in HDF5/NetCDF4 container.
# --------------------------------------------------------------------------
CCMP = {
    "base_url": "https://data.remss.com/ccmp/v03.1",
    "variables": ["uwnd", "vwnd"],   # 10 m zonal / meridional wind (m/s)
    "url": "{base}/Y{year}/M{month:02d}/CCMP_Wind_Analysis_{ymd}_V03.1_L4.nc",
}
CCMP_RAW = DATA_RAW / "ccmp"
CCMP_RAW.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Model input channels (surface observations) -- Day 3+
# --------------------------------------------------------------------------
INPUT_CHANNELS = [
    "sst",    # OSTIA  (PS66: SST)
    "sss",    # SMAP+SMOS L4 multi-observation  (PS66: SSS)
    "sla",    # DUACS  (PS66: SSH)
    "ugos",   # DUACS geostrophic surface current  (PS66: Currents)
    "vgos",
    "uwnd",   # CCMP v3.1 (PS66: Winds)
    "vwnd",
]
