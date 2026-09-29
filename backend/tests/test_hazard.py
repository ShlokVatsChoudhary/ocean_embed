"""Contract and physics tests for the ocean-hazard diagnostics.

These pin the properties that make the hazard layer safe to publish:

* the integrations are analytically correct on a linear profile,
* a truncated profile is reported as NO VALUE rather than as a low TCHP,
  because a low TCHP near a coast reads as "low cyclone risk",
* land stays missing, and every payload carries its provenance and caveat.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from app.core.constants import STANDARD_DEPTHS
from app.science.hazard import (
    CATEGORY_BREAKS,
    J_M2_TO_KJ_CM2,
    MIN_VALID_DEPTH,
    RHO_CP,
    d26,
    hazard_fields,
    mld,
    ohc,
    tchp,
    tchp_category,
    thermocline_depth,
    valid_profile_mask,
)

SIMPLE_DEPTHS = np.array([0.0, 100.0])


def _column(values, depths):
    """Turn a 1-D profile into a (Z, 1, 1) field."""
    return np.asarray(values, dtype="float64").reshape(-1, 1, 1)


# ------------------------------------------------------------------ physics
def test_tchp_matches_the_analytic_integral_on_a_linear_profile():
    # 30 C at the surface falling linearly to 20 C at 100 m. The 26 C isotherm sits at
    # 40 m, so TCHP is the integral of (T - 26) from 0 to 40 m = 80 K.m exactly.
    T = _column([30.0, 20.0], SIMPLE_DEPTHS)
    expected = RHO_CP * 80.0 * J_M2_TO_KJ_CM2
    assert tchp(T, SIMPLE_DEPTHS)[0, 0] == pytest.approx(expected, rel=1e-12)
    # 1025 * 3985 * 80 * 1e-7 = 32.677 kJ/cm^2
    assert tchp(T, SIMPLE_DEPTHS)[0, 0] == pytest.approx(32.677, rel=1e-4)


def test_d26_matches_the_analytic_crossing_depth():
    T = _column([30.0, 20.0], SIMPLE_DEPTHS)
    # 26 C is exactly 40 % of the way from 30 down to 20.
    assert d26(T, SIMPLE_DEPTHS)[0, 0] == pytest.approx(40.0, abs=1e-9)


def test_ohc_matches_the_analytic_integral():
    # Uniform 20 C over 0-100 m relative to 0 C: 20 K * 100 m.
    T = _column([20.0, 20.0], SIMPLE_DEPTHS)
    expected = RHO_CP * 20.0 * 100.0 * J_M2_TO_KJ_CM2
    assert ohc(T, SIMPLE_DEPTHS)[0, 0] == pytest.approx(expected, rel=1e-12)


def test_ohc_clipping_interpolates_instead_of_using_the_far_endpoint():
    """A segment straddling zmax must interpolate, not reuse the endpoint temperature.

    With a steeply falling profile, reusing the 5 C endpoint over a clipped length
    would understate the integral. This is the bug the interpolation prevents.
    """
    T = _column([30.0, 10.0], SIMPLE_DEPTHS)  # linear, 0.2 C per metre
    clipped = ohc(T, SIMPLE_DEPTHS, zmax=50.0)[0, 0]
    # Mean temperature over 0-50 m is 25 C, so OHC = rho_cp * 25 * 50.
    expected = RHO_CP * 25.0 * 50.0 * J_M2_TO_KJ_CM2
    assert clipped == pytest.approx(expected, rel=1e-12)

    # Using the 10 C endpoint over 50 m would give 20 C mean instead of 25 C.
    wrong = RHO_CP * 20.0 * 50.0 * J_M2_TO_KJ_CM2
    assert clipped > wrong


def test_tchp_handles_a_warm_subsurface_layer():
    """Bay of Bengal temperature inversions: a warm layer below a cool one must count.

    The convention is the integral of positive excess max(T - 26, 0) dz.
    """
    # 28 C at surface, 25 C at 50 m, 27 C at 100 m.
    depths = np.array([0.0, 50.0, 100.0])
    T = _column([28.0, 25.0, 27.0], depths)
    value = tchp(T, depths)[0, 0]

    # Descending segment: excess 2 -> -1 over 0-50 m, so the 26 C crossing is at
    # 2/3 * 50 = 33.333 m and the positive part is 0.5 * 2 * 33.333 = 33.333 K.m.
    # Ascending segment: excess -1 -> +1 over 50-100 m, so the positive part starts
    # at 75 m and is 0.5 * 1 * 25 = 12.5 K.m.  The sub-26 C stretch contributes 0.
    expected_excess = 0.5 * 2.0 * (2.0 / 3.0 * 50.0) + 0.5 * 1.0 * 25.0
    assert value == pytest.approx(RHO_CP * expected_excess * J_M2_TO_KJ_CM2, rel=1e-12)

    # Equivalently, the trapezoid rule on max(T - 26, 0) must reproduce the same number.
    assert value == pytest.approx(RHO_CP * 45.833333333333336 * J_M2_TO_KJ_CM2, rel=1e-9)

    # A naive "clip the values to zero, then trapezoid over the full segment" reference
    # would give 75.0 K.m, because zeroing a segment endpoint still spreads the trapezoid
    # across the whole segment. The correct integral is strictly smaller than that.
    naive = np.trapezoid(np.clip(np.array([28.0, 25.0, 27.0]) - 26.0, 0.0, None), depths)
    assert naive == pytest.approx(75.0, rel=1e-12)
    assert value < RHO_CP * naive * J_M2_TO_KJ_CM2


def test_mld_uses_the_temperature_threshold_criterion():
    # Surface 28 C, threshold 27.8 C, reached at 20 % of the way from 28 to 27 at 100 m.
    T = _column([28.0, 27.0], SIMPLE_DEPTHS)
    assert mld(T, SIMPLE_DEPTHS)[0, 0] == pytest.approx(20.0, abs=1e-9)


def test_thermocline_depth_finds_the_steepest_segment():
    depths = np.array([0.0, 50.0, 100.0, 200.0])
    # Steepest is 50-100 m (0.2 C/m).
    T = _column([28.0, 27.0, 17.0, 15.0], depths)
    assert thermocline_depth(T, depths)[0, 0] == pytest.approx(75.0)


def test_tchp_category_breaks_are_inclusive_at_the_threshold():
    field = np.array([[10.0, 30.0, 50.0, 80.0, 120.0, np.nan]])
    got = tchp_category(field)[0]
    assert got[:5].tolist() == [0.0, 1.0, 2.0, 3.0, 3.0]
    assert np.isnan(got[5])
    assert CATEGORY_BREAKS == (30.0, 50.0, 80.0)


# ------------------------------------------- the safety property that matters
def test_truncated_profile_is_reported_as_no_value_not_as_a_low_tchp():
    """The critical property. A shelf column finite only to 50 m must NOT yield a number.

    Reporting the partial integral would understate TCHP, and understated TCHP beside a
    coastline reads as low cyclone risk -- the wrong direction of error for a warning.
    """
    T = np.full((len(STANDARD_DEPTHS), 1, 1), np.nan)
    shallow = STANDARD_DEPTHS.index(50.0)
    # A warm 30 C column, but only down to 50 m.
    T[: shallow + 1, 0, 0] = 30.0

    assert not valid_profile_mask(T, np.asarray(STANDARD_DEPTHS))[0, 0]
    fields = hazard_fields(T, np.asarray(STANDARD_DEPTHS))
    assert np.isnan(fields["tchp"][0, 0])
    assert np.isnan(fields["d26"][0, 0])
    assert np.isnan(fields["ohc"][0, 0])
    assert np.isnan(fields["mld"][0, 0])
    assert np.isnan(fields["tchp_category"][0, 0])


def test_valid_profile_mask_accepts_a_complete_column_and_rejects_land():
    depths = np.asarray(STANDARD_DEPTHS)
    complete = np.full((len(STANDARD_DEPTHS), 1, 1), 25.0)
    assert valid_profile_mask(complete, depths)[0, 0]

    land = np.full((len(STANDARD_DEPTHS), 1, 1), np.nan)
    assert not valid_profile_mask(land, depths)[0, 0]


def test_hazards_stay_missing_over_land():
    depths = np.asarray(STANDARD_DEPTHS)
    land = np.full((len(STANDARD_DEPTHS), 2, 2), np.nan)
    fields = hazard_fields(land, depths)
    for key in ("tchp", "d26", "ohc", "mld", "thermocline_depth", "tchp_category"):
        assert np.isnan(fields[key]).all(), key


def test_hazards_are_masked_even_where_the_raw_function_would_return_a_number():
    """hazard_fields must apply the mask, not just report it."""
    depths = np.asarray(STANDARD_DEPTHS)
    T = np.full((len(STANDARD_DEPTHS), 1, 1), np.nan)
    T[: depths.tolist().index(50.0) + 1, 0, 0] = 29.0
    # The unmasked function happily returns a (wrong) number...
    assert np.isfinite(tchp(T, depths)[0, 0])
    # ...but the field-level entry point must not.
    assert np.isnan(hazard_fields(T, depths)["tchp"][0, 0])


def test_min_valid_depth_covers_the_basin_diagnostics():
    """The 300 m floor must be deeper than any realistic 26 C isotherm or mixed layer."""
    assert MIN_VALID_DEPTH >= 200.0


# ---------------------------------------------------------------- endpoints
@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def test_hazard_variables_endpoint_lists_every_diagnostic(client):
    response = client.get("/api/hazard/variables")
    assert response.status_code == 200
    names = {item["variable"] for item in response.json()}
    assert {"tchp", "d26", "ohc", "mld", "thermocline_depth"} <= names


def test_hazard_summary_reports_coverage_and_cyclone_counts(client):
    response = client.get("/api/hazard/summary", params={"date": "2020-01-01"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "available"
    assert body["valid_cells"] > 0
    assert body["coverage"] == pytest.approx(body["valid_cells"] / body["total_cells"])
    assert body["favourable_cells"] >= body["rapid_intensification_cells"]
    metrics = {item["variable"] for item in body["metrics"]}
    assert {"tchp", "d26", "ohc", "mld", "thermocline_depth"} == metrics


def test_hazard_field_payload_carries_provenance_and_caveat(client):
    response = client.get("/api/hazard", params={"date": "2020-01-01", "variable": "tchp"})
    assert response.status_code == 200
    body = response.json()
    assert body["variable"] == "tchp"
    assert body["unit"] == "kJ/cm^2"
    assert body["category_breaks"] == list(CATEGORY_BREAKS)
    assert len(body["values"]) == 101
    assert len(body["values"][0]) == 241
    # The caveat must say plainly that this is not an operational forecast.
    assert "not an operational hazard forecast" in body["caveat"]
    assert body["caveat"].strip()
    assert body["provenance"].strip()
    assert body["min_valid_depth_m"] == MIN_VALID_DEPTH


def test_hazard_field_uses_null_not_zero_for_missing_cells(client):
    response = client.get("/api/hazard", params={"date": "2020-01-01", "variable": "tchp"})
    body = response.json()
    flat = [value for row in body["values"] for value in row]
    missing = [value for value in flat if value is None]
    # Plenty of cells are land or too-shallow shelf; they must be null, never 0.
    assert missing, "expected some missing cells"
    assert all(value is None for value in missing)


def test_hazard_rejects_an_out_of_range_date(client):
    response = client.get("/api/hazard", params={"date": "2021-06-01", "variable": "tchp"})
    assert response.status_code == 400


def test_hazard_rejects_an_unknown_variable(client):
    response = client.get("/api/hazard", params={"date": "2020-01-01", "variable": "nonsense"})
    assert response.status_code == 400
    assert "Unknown hazard variable" in response.json()["detail"]
