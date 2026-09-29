"""Derived ocean-hazard diagnostics from subsurface temperature profiles.

Turns a model temperature column T(z) into the quantities cyclone forecasters use:

  * TCHP            -- Tropical Cyclone Heat Potential (cyclone fuel)
  * D26             -- depth of the 26 C isotherm
  * OHC             -- Ocean Heat Content relative to a reference, to a fixed depth
  * MLD             -- mixed-layer depth (0.2 C criterion)
  * thermocline     -- depth of the maximum vertical temperature gradient

All routines take the temperature field with the depth axis FIRST:

        T : (Z, H, W)          NaN over land
        depths : (Z,)

They are pure NumPy so they run on CPU, and exact for piecewise-linear profiles
because each standard-depth segment is integrated analytically.

Why a validity mask exists
--------------------------
A truncated profile must NOT be integrated. The model masks cells where the sea
floor is shallower than the requested depth, so on a shelf a column may be finite
at 0-50 m and NaN below. Integrating only the valid part returns a TCHP that is
biased LOW, and a low TCHP near a coastline means "low cyclone risk" -- the exact
wrong direction of error for a warning product. So any column that is not finite
all the way to ``MIN_VALID_DEPTH`` is reported as NaN (no value) rather than as a
small number. Coverage is reported alongside so the loss is visible, not hidden.

300 m is used as the floor because the deepest 26 C isotherm, mixed layer and
thermocline in this basin all sit well above it. Excluding shallower columns
therefore costs no real information.

References
----------
Leipper & Volgenau (1972), "Hurricane heat potential of the Gulf of Mexico",
J. Phys. Oceanogr. -- the original TCHP definition.

Price (1981); Shay et al. (2000) -- relationship between upper-ocean heat content
and tropical cyclone intensification.
"""
from __future__ import annotations

import numpy as np

# Physical constants (seawater).
RHO = 1025.0            # kg m^-3
CP = 3985.0             # J kg^-1 K^-1
RHO_CP = RHO * CP       # J m^-3 K^-1
J_M2_TO_KJ_CM2 = 1e-7   # 1 J/m^2 = 1e-7 kJ/cm^2
TREF = 26.0             # reference isotherm for TCHP / D26

#: A column must be finite to at least this depth to produce a hazard value.
MIN_VALID_DEPTH = 300.0

#: TCHP category breaks in kJ/cm^2, and their labels.
CATEGORY_BREAKS = (30.0, 50.0, 80.0)
CATEGORY_LABELS = (
    "< 30   low",
    "30-50  moderate",
    "50-80  favourable for intensification",
    "> 80   rapid-intensification potential",
)

#: Depth to which OHC is integrated by default.
OHC_ZMAX = 300.0


def valid_profile_mask(T: np.ndarray, depths, min_depth: float = MIN_VALID_DEPTH) -> np.ndarray:
    """Column is usable only if finite at every standard depth down to ``min_depth``.

    This is what stops a truncated shelf profile from being reported as a small
    TCHP. See the module docstring.
    """
    d = np.asarray(depths, dtype=float)
    idx = np.where(d <= min_depth)[0]
    if idx.size == 0:
        idx = np.array([0])
    return np.isfinite(T[idx]).all(axis=0)


def _cross_depth(T, depths, level, *, first=True):
    """Depth where a profile crosses ``level``.

    ``T`` is (Z, H, W). Returns (H, W) depths in metres.
      ``first=True``  -> shallowest crossing (used for D26, MLD)
      ``first=False`` -> deepest crossing

    A crossing is only registered on a segment that goes from above ``level`` to
    at-or-below it.
    """
    d = np.asarray(depths, dtype=float)
    Z = T.shape[0]
    excess = T - level
    H, W = T.shape[1], T.shape[2]
    out = np.full((H, W), np.nan)

    # Surface already at or below the level.
    out = np.where(np.isfinite(excess[0]) & (excess[0] <= 0), 0.0, out)
    # Entire profile above the level: report the deepest requested depth.
    all_above = np.isfinite(excess).all(axis=0) & (excess > 0).all(axis=0)
    out = np.where(all_above, d[-1], out)

    segs = range(Z - 1) if first else range(Z - 2, -1, -1)
    for i in segs:
        e0, e1 = excess[i], excess[i + 1]
        dz = d[i + 1] - d[i]
        cross = (e0 > 0) & (e1 <= 0) & np.isnan(out)
        denom = e0 - e1
        frac = np.where(np.abs(denom) > 0, e0 / np.where(denom == 0, 1, denom), 0)
        out = np.where(cross, d[i] + frac * dz, out)
    return out


def tchp(T, depths, tref: float = TREF):
    """Tropical Cyclone Heat Potential (kJ/cm^2).

    The convention used here is the vertical integral of the positive excess
    ``max(T - tref, 0)`` over the profile, which equals the classical
    Leipper & Volgenau integral when the profile crosses the isotherm once.

    The two differ only when a warm layer sits BELOW a cool layer -- a real
    feature of the Bay of Bengal's freshwater-capped inversions. In that case
    this formulation counts the deeper warm layer as available heat, which is
    the intent for a cyclone-fuel diagnostic, while ``d26`` still reports the
    depth of the first crossing. The two are deliberate and consistent.
    """
    d = np.asarray(depths, dtype=float)
    Z = T.shape[0]
    integral = np.zeros(T.shape[1:], dtype=float)  # K * m

    for i in range(Z - 1):
        e0 = T[i] - tref
        e1 = T[i + 1] - tref
        dz = d[i + 1] - d[i]

        full = (e0 > 0) & (e1 > 0)
        down = (e0 > 0) & (e1 <= 0)
        rise = (e0 <= 0) & (e1 > 0)

        # Whole segment above the isotherm.
        integral = integral + np.where(full, 0.5 * (e0 + e1) * dz, 0.0)

        # Descending crossing: integrate from the segment top to the crossing.
        denom = e0 - e1
        frac = np.where(np.abs(denom) > 0, e0 / np.where(denom == 0, 1, denom), 0)
        integral = integral + np.where(down, 0.5 * e0 * (frac * dz), 0.0)

        # Ascending crossing: integrate from the crossing to the segment base.
        denom2 = e1 - e0
        frac2 = np.where(np.abs(denom2) > 0, -e0 / np.where(denom2 == 0, 1, denom2), 0)
        integral = integral + np.where(rise, 0.5 * e1 * ((1 - frac2) * dz), 0.0)

    value = RHO_CP * integral * J_M2_TO_KJ_CM2
    return np.where(np.isfinite(T[0]), value, np.nan)


def d26(T, depths, tref: float = TREF):
    """Depth (m) of the 26 C isotherm."""
    return _cross_depth(T, depths, tref, first=True)


def ohc(T, depths, *, ref: float = 0.0, zmax: float = OHC_ZMAX, rho_cp: float = RHO_CP):
    """Ocean Heat Content (kJ/cm^2) relative to ``ref``, integrated to ``zmax``.

    A segment that straddles ``zmax`` is clipped AND its temperature is
    interpolated at the clip depth. Using the unclipped endpoint temperature over
    a clipped length would be the wrong trapezoid. With the default standard
    depths ``zmax`` lands exactly on 300 m so no clipping occurs, but the
    interpolation keeps the function correct for any other depth grid.
    """
    d = np.asarray(depths, dtype=float)
    Z = T.shape[0]
    integral = np.zeros(T.shape[1:], dtype=float)

    for i in range(Z - 1):
        z0 = d[i]
        if z0 >= zmax:
            break
        z1 = min(d[i + 1], zmax)
        dz = z1 - z0
        if dz <= 0:
            continue

        T0 = T[i]
        if d[i + 1] > zmax:
            weight = (z1 - z0) / (d[i + 1] - z0)
            T1 = T0 + weight * (T[i + 1] - T0)
        else:
            T1 = T[i + 1]

        seg = 0.5 * ((T0 - ref) + (T1 - ref)) * dz
        # NaN contributes nothing here; invalid columns are masked at the end.
        integral = integral + np.where(np.isfinite(seg), seg, 0.0)

    value = rho_cp * integral * J_M2_TO_KJ_CM2
    return np.where(np.isfinite(T[0]), value, np.nan)


def _mld_impl(T, depths, level_field):
    """Depth where T first drops below a per-column threshold."""
    d = np.asarray(depths, dtype=float)
    Z = T.shape[0]
    out = np.full(T.shape[1:], np.nan)
    out = np.where(np.isfinite(T[0]) & (T[0] <= level_field), 0.0, out)
    all_above = np.isfinite(T).all(axis=0) & (T > level_field).all(axis=0)
    out = np.where(all_above, d[-1], out)

    for i in range(Z - 1):
        e0 = T[i] - level_field
        e1 = T[i + 1] - level_field
        dz = d[i + 1] - d[i]
        cross = (e0 > 0) & (e1 <= 0) & np.isnan(out)
        denom = e0 - e1
        frac = np.where(np.abs(denom) > 0, e0 / np.where(denom == 0, 1, denom), 0)
        out = np.where(cross, d[i] + frac * dz, out)
    return out


def mld(T, depths, dtemp: float = 0.2):
    """Mixed-layer depth (m) using a ``dtemp`` criterion from the surface."""
    return _mld_impl(T, depths, T[0] - dtemp)


def thermocline_depth(T, depths):
    """Depth (m) of the maximum vertical temperature gradient."""
    d = np.asarray(depths, dtype=float)
    grad = np.abs(np.diff(T, axis=0)) / np.diff(d)[:, None, None]
    grad = np.where(np.isfinite(grad), grad, -1.0)
    idx = np.argmax(grad, axis=0)
    mid = 0.5 * (d[:-1] + d[1:])
    out = mid[idx]
    return np.where(np.isfinite(T[0]), out, np.nan)


def tchp_category(tchp_field):
    """Map TCHP (kJ/cm^2) to an integer 0-3 intensification category."""
    t = np.asarray(tchp_field, dtype=float)
    cat = np.zeros(t.shape, dtype=float)
    for cut, value in zip(CATEGORY_BREAKS, (1, 2, 3)):
        cat = np.where(t >= cut, float(value), cat)
    return np.where(np.isfinite(t), cat, np.nan)


def hazard_fields(T, depths, *, min_depth: float = MIN_VALID_DEPTH):
    """Compute every hazard diagnostic for a field, masked to valid columns.

    Returns a dict of ``(H, W)`` arrays plus the validity mask. Columns that are
    not finite to ``min_depth`` are NaN in every returned metric.
    """
    mask = valid_profile_mask(T, depths, min_depth=min_depth)
    out = {
        "tchp": tchp(T, depths),
        "d26": d26(T, depths),
        "ohc": ohc(T, depths, zmax=min(min_depth, OHC_ZMAX)),
        "mld": mld(T, depths),
        "thermocline_depth": thermocline_depth(T, depths),
        "valid_mask": mask,
    }
    for key in ("tchp", "d26", "ohc", "mld", "thermocline_depth"):
        out[key] = np.where(mask, out[key], np.nan)
    out["tchp_category"] = tchp_category(out["tchp"])
    return out


#: Display metadata for each hazard variable.
VARIABLE_INFO = {
    "tchp": ("Tropical Cyclone Heat Potential", "kJ/cm^2"),
    "d26": ("Depth of the 26 °C isotherm", "m"),
    "ohc": ("Ocean Heat Content (0–300 m, rel. 0 °C)", "kJ/cm^2"),
    "mld": ("Mixed-layer depth (0.2 °C criterion)", "m"),
    "thermocline_depth": ("Thermocline depth (max gradient)", "m"),
    "tchp_category": ("TCHP intensification category", "category"),
}
