"""Derived ocean-hazard diagnostics computed from subsurface temperature profiles.

These turn the model's raw T(z) into quantities that forecasters actually use:

  * TCHP  -- Tropical Cyclone Heat Potential  (cyclone fuel)
  * D26   -- depth of the 26 C isotherm
  * OHC   -- Ocean Heat Content (relative to a reference, to a fixed depth)
  * MLD   -- mixed-layer depth (0.2 C criterion)
  * thermocline depth (max vertical gradient)

All routines take a temperature field with the DEPTH axis first:

        T : (Z, H, W)          (NaN over land)
        depths : (Z,)

and are pure NumPy so they run on CPU. They are exact for piecewise-linear
profiles because each standard-depth segment is integrated analytically.

References
----------
Leipper & Volgenau (1972), "Hurricane heat potential of the Gulf of Mexico",
J. Phys. Oceanogr.  --  original TCHP definition.
"""
from __future__ import annotations

import numpy as np

# physical constants (seawater)
RHO = 1025.0          # kg m^-3
CP = 3985.0           # J kg^-1 K^-1
RHO_CP = RHO * CP     # J m^-3 K^-1
J_M2_TO_KJ_CM2 = 1e-7  # 1 J/m^2 = 1e-7 kJ/cm^2
TREF = 26.0           # reference for TCHP / D26


def _cross_depth(T, depths, level, *, first=True):
    """Depth where the profile crosses `level`.

    T : (Z, H, W).  Returns (H, W) depth in metres.
      - `first=True`  -> shallowest crossing  (used for D26, MLD)
      - `first=False` -> deepest crossing
    A crossing is found only on a segment where the profile goes from
    above `level` to at-or-below it.
    """
    d = np.asarray(depths, float)
    Z = T.shape[0]
    excess = T - level                       # (Z,H,W)
    H, W = T.shape[1], T.shape[2]
    out = np.full((H, W), np.nan)

    # default: surface already below level -> 0 m
    out = np.where(np.isfinite(excess[0]) & (excess[0] <= 0), 0.0, out)
    # default: whole profile above level -> deepest requested depth
    allabove = np.isfinite(excess).all(axis=0) & (excess > 0).all(axis=0)
    out = np.where(allabove, d[-1], out)

    segs = range(Z - 1) if first else range(Z - 2, -1, -1)
    for i in segs:
        e0, e1 = excess[i], excess[i + 1]
        dz = d[i + 1] - d[i]
        cross = (e0 > 0) & (e1 <= 0) & np.isnan(out)
        denom = (e0 - e1)
        frac = np.where(np.abs(denom) > 0, e0 / np.where(denom == 0, 1, denom), 0)
        z = d[i] + frac * dz
        out = np.where(cross, z, out)
    return out


def tchp(T, depths, tref: float = TREF):
    """Tropical Cyclone Heat Potential (kJ/cm^2).

    Integral of (T - tref) from the surface down to the depth where the
    profile first drops to `tref`.
    """
    d = np.asarray(depths, float)
    Z = T.shape[0]
    integral = np.zeros(T.shape[1:], dtype=float)          # K * m
    for i in range(Z - 1):
        e0 = T[i] - tref
        e1 = T[i + 1] - tref
        dz = d[i + 1] - d[i]
        full = (e0 > 0) & (e1 > 0)
        cross = (e0 > 0) & (e1 <= 0)
        rise = (e0 <= 0) & (e1 > 0)
        # full segment
        integral = integral + np.where(full, 0.5 * (e0 + e1) * dz, 0.0)
        # descending crossing: integrate up to z_c
        denom = e0 - e1
        frac = np.where(np.abs(denom) > 0, e0 / np.where(denom == 0, 1, denom), 0)
        integral = integral + np.where(cross, 0.5 * e0 * (frac * dz), 0.0)
        # ascending crossing: integrate from z_c to end
        denom2 = e1 - e0
        frac2 = np.where(np.abs(denom2) > 0, -e0 / np.where(denom2 == 0, 1, denom2), 0)
        integral = integral + np.where(rise, 0.5 * e1 * ((1 - frac2) * dz), 0.0)

    val = RHO_CP * integral * J_M2_TO_KJ_CM2
    val = np.where(np.isfinite(T[0]), val, np.nan)          # land -> NaN
    return val


def d26(T, depths, tref: float = TREF):
    """Depth (m) of the tref (26 C) isotherm."""
    return _cross_depth(T, depths, tref, first=True)


def ohc(T, depths, *, ref: float = 0.0, zmax: float = 300.0,
        rho_cp: float = RHO_CP):
    """Ocean Heat Content (kJ/cm^2) relative to `ref`, integrated to `zmax`."""
    d = np.asarray(depths, float)
    Z = T.shape[0]
    integral = np.zeros(T.shape[1:], dtype=float)
    for i in range(Z - 1):
        z0, z1 = d[i], d[i + 1]
        if z0 >= zmax:
            break
        z1 = min(z1, zmax)
        dz = z1 - z0
        e0 = T[i] - ref
        e1 = T[i + 1] - ref
        val = 0.5 * (e0 + e1) * dz
        integral = integral + np.where(np.isfinite(val), val, 0.0)
    out = rho_cp * integral * J_M2_TO_KJ_CM2
    out = np.where(np.isfinite(T[0]), out, np.nan)
    return out


def mld(T, depths, dtemp: float = 0.2):
    """Mixed-layer depth (m) using the dtemp criterion from the surface."""
    thresh = T[0] - dtemp
    return _mld_impl(T, depths, thresh)


def _mld_impl(T, depths, level_field):
    """Depth where T drops below a per-column threshold (H,W) array."""
    d = np.asarray(depths, float)
    Z = T.shape[0]
    out = np.full(T.shape[1:], np.nan)
    out = np.where(np.isfinite(T[0]) & (T[0] <= level_field), 0.0, out)
    allabove = np.isfinite(T).all(axis=0) & (T > level_field).all(axis=0)
    out = np.where(allabove, d[-1], out)
    for i in range(Z - 1):
        e0 = T[i] - level_field
        e1 = T[i + 1] - level_field
        dz = d[i + 1] - d[i]
        cross = (e0 > 0) & (e1 <= 0) & np.isnan(out)
        denom = e0 - e1
        frac = np.where(np.abs(denom) > 0, e0 / np.where(denom == 0, 1, denom), 0)
        out = np.where(cross, d[i] + frac * dz, out)
    return out


def thermocline_depth(T, depths):
    """Depth (m) of the maximum vertical temperature gradient."""
    d = np.asarray(depths, float)
    grad = np.abs(np.diff(T, axis=0)) / np.diff(d)[:, None, None]
    grad = np.where(np.isfinite(grad), grad, -1.0)
    idx = np.argmax(grad, axis=0)
    mid = 0.5 * (d[:-1] + d[1:])
    out = mid[idx]
    out = np.where(np.isfinite(T[0]), out, np.nan)
    return out


def tchp_category(tchp_field):
    """Map TCHP (kJ/cm^2) to a 0-3 cyclone-support category."""
    t = tchp_field
    cat = np.zeros_like(t)
    cat = np.where(t >= 30, 1, cat)
    cat = np.where(t >= 50, 2, cat)
    cat = np.where(t >= 80, 3, cat)
    cat = np.where(np.isfinite(t), cat, np.nan)
    return cat


CATEGORY_LABELS = ["< 30  low", "30-50  moderate", "50-80  favourable",
                   "> 80  rapid-intensification"]
