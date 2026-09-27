"""Tests for the honest metric aggregation in `src.metrics`.

The unweighted mean over depth levels is dominated by the four shallowest
levels and mixes per-level masks of different size. These tests pin the
helpers that report comparable numbers instead.

Run standalone (`python tests/test_metrics.py`) or under pytest. No data.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, metrics as ev  # noqa: E402

Z, H, W = len(config.DEPTHS), 4, 5


def _perfect_with_holes():
    """Truth finite everywhere at the surface, but masked below 50 m.

    Returns (pred, true) where pred == true, so every metric that is computed
    over the surviving cells must be exactly zero.
    """
    rng = np.random.default_rng(0)
    true = rng.normal(20.0, 4.0, size=(3, Z, H, W)).astype("float32")
    # mask everything deeper than 50 m in half the columns
    deep = np.array(config.DEPTHS) > 50
    true[:, deep, :, 2:] = np.nan
    pred = true.copy()
    return pred, true


def test_perfect_prediction_scores_zero():
    pred, true = _perfect_with_holes()
    m = ev.per_depth_metrics(pred, true)
    assert np.nanmax(np.abs(m["rmse"])) < 1e-6
    assert np.nanmax(np.abs(m["bias"])) < 1e-6


def test_band_mean_selects_the_right_levels():
    m = {"depth": np.array(config.DEPTHS),
         "rmse": np.arange(Z, dtype=float)}
    # levels >= 50 m are indices 5..14
    assert abs(ev.band_mean(m, "rmse", lo=50) - np.mean(np.arange(5, Z))) < 1e-9
    # the thermocline band 50-200 m is indices 5..10
    assert abs(ev.band_mean(m, "rmse", lo=50, hi=200)
               - np.mean(np.arange(5, 11))) < 1e-9
    # a band with no levels returns NaN rather than raising
    assert np.isnan(ev.band_mean(m, "rmse", lo=5000, hi=6000))


def test_common_mask_uses_one_cell_set_for_every_level():
    """With the common mask, each level is scored on the same number of cells."""
    rng = np.random.default_rng(1)
    true = rng.normal(20.0, 4.0, size=(3, Z, H, W)).astype("float32")
    # a different, depth-dependent hole pattern: naively this makes deep levels
    # easier, which is exactly the artefact the common mask removes
    for zi in range(Z):
        true[:, zi, :, : int(zi % W)] = np.nan
    pred = true + 1.0            # constant error -> RMSE must be 1 everywhere

    naive = ev.per_depth_metrics(pred, true)
    common = ev.common_mask_metrics(pred, true)

    assert np.allclose(naive["rmse"], 1.0), "constant error should be exact"
    # common mask keeps only cells finite at ALL depths: column 0 is always
    # masked (zi % W == 0 for zi in 0, 5, 10), so W-1 columns survive
    n_naive = np.array([np.isfinite(true[:, zi]).sum() for zi in range(Z)])
    assert not np.all(n_naive == n_naive[0]), "test needs a moving mask"
    assert np.allclose(common["rmse"], 1.0)
    # every level scored on the same (reduced) cell count
    counts = np.array([np.isfinite(np.where(
        np.isfinite(true).all(axis=1, keepdims=True), true, np.nan)[:, zi]).sum()
        for zi in range(Z)])
    assert np.all(counts == counts[0])


def test_headline_reports_expected_keys():
    pred, true = _perfect_with_holes()
    h = ev.headline(ev.common_mask_metrics(pred, true))
    for k in ("rmse_all", "rmse_ge50", "rmse_thermocline", "bias_ge50",
              "corr_all", "corr_ge50"):
        assert k in h
        assert np.isfinite(h[k])


def test_wins_vs_is_per_level():
    m1 = {"rmse": np.array([1.0, 2.0, 3.0])}
    m2 = {"rmse": np.array([0.5, 2.5, 2.0])}
    w = ev.wins_vs(m1, m2)
    assert w.tolist() == [True, False, True]


def test_print_headline_runs():
    pred, true = _perfect_with_holes()
    ev.print_headline(pred, true, "dummy", common=True)
    ev.print_headline(pred, true, "dummy", common=False)


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
