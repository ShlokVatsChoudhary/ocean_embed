"""Independent ARGO check restricted to the GENUINE temporal holdout (last 73 days of 2020)."""
import sys, os, numpy as np, pandas as pd, tensorflow as tf, xarray as xr
MODEL_DIR = "/Users/yogchhablani/Downloads/PS66-Ocean-Model-9ch"
sys.path.insert(0, MODEL_DIR); os.chdir(MODEL_DIR)
from src import data, argo, harmonize
from src import model as M
from src.config import DEPTHS

X, Y, stats, channels = data.load_arrays("2020_9ch")
ch5 = [str(c) for c in channels[:5]]
T = X.shape[0]; lo = T - T // 5
depths = np.asarray(DEPTHS, float)

# ---- ARGO, canonical pipeline (strip fill, standard depths, regrid to target) ----
P = os.path.join(MODEL_DIR, "data/raw/argo_2020.nc")
ds = xr.open_dataset(P, mask_and_scale=False)
tvar = next(v for v in ("T_ANALYZED", "temp", "temperature") if v in ds)
Tv = ds[tvar]; a = Tv.values.astype("float64")
fill = Tv.attrs.get("_FillValue", Tv.attrs.get("missing_value"))
if fill is not None and np.isscalar(fill) and np.isfinite(fill): a[a == fill] = np.nan
a[np.abs(a) > 1e4] = np.nan
da = xr.DataArray(a.astype("float32"), dims=Tv.dims, coords=Tv.coords, name="temp")
if "ZAX" in da.dims: da = da.rename({"ZAX": "depth"})
da = harmonize._to_standard_depths(da)
da = argo.regrid_to_target(da)
days = pd.date_range("2020-01-01", "2020-12-31", freq="D").values
AR = da.sel({"time": days}, method="nearest").transpose("time", ...).values
AR = np.where(np.isfinite(AR), AR, np.nan)
print(f"ARGO field {AR.shape}  finite={np.isfinite(AR).mean()*100:.1f}%  (full year)")

# ---- model predictions ----
Xn, _ = data.normalize(X[:, :5], Y, stats, ch5); Xn = np.nan_to_num(Xn, nan=0.0).astype("float32")
m = M.OceanModel(cin=5, D=256, Z=15); _ = m(tf.zeros([1, 5, 101, 241]))
m.load_weights("weights/model_2020.weights.h5")
out = []
for i in range(0, T, 8):
    out.append(m(Xn[i:i+8], training=False)[0].numpy())
pred = np.concatenate(out) * stats["y_std"] + stats["y_mean"]
pred = np.where(np.isfinite(Y), pred, np.nan)
print(f"model field {pred.shape}  params={m.count_params():,}")

fair = np.full_like(Y, np.nan); fair[1:] = Y[:-1]        # day-before persistence (GLORYS)
times = np.arange(T).astype("timedelta64[D]") + np.datetime64("2020-01-01")
train_mask = np.zeros(T, bool); train_mask[:lo] = True
from src import baselines as B
clim = B.fit_climatology(Y, times, train_mask)
clm = B.predict_climatology(clim, times)

zz = depths[:, None, None]
def rep(nm, Pf):
    ok = np.isfinite(Pf) & np.isfinite(AR)
    def r(sel, win):
        s = ok & np.broadcast_to(sel, AR.shape) & win[:, None, None, None]
        d = (Pf - AR)[s]
        return np.sqrt((d ** 2).mean()), float(np.nanmean(d))
    win_h = np.zeros(T, bool); win_h[lo:] = True
    win_t = np.zeros(T, bool); win_t[:lo] = True
    o1 = np.ones(zz.shape, dtype=bool)
    line = []
    for sel in (o1, zz >= 50, (zz >= 50) & (zz <= 200)):
        rh, bh = r(sel, win_h); rt, _ = r(sel, win_t)
        line += [rh, rt, bh]
    print(f"{nm:<32} {line[0]:7.3f} {line[3]:7.3f} {line[6]:7.3f} | "
          f"{line[1]:8.3f} {line[4]:7.3f} {line[7]:7.3f}   (bias HO all={line[2]:+.3f})")
    return line

print("\n=== vs INDEPENDENT ARGO 2020 ===")
print(f"{'method':<32} {'all':>7} {'>=50m':>7} {'therm':>7} | {'all':>8} {'>=50m':>7} {'therm':>7}")
rep("OceanEmbed", pred)
rep("persistence (prev. GLORYS day)", fair)
rep("climatology (from train days)", np.broadcast_to(clm, Y.shape).astype("float32"))
