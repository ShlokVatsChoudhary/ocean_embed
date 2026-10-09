import numpy as np, tensorflow as tf
from common import configure_model_root

MODEL_DIR = configure_model_root()
from src import data
from src import model as M
from src.config import DEPTHS

X, Y, stats, channels = data.load_arrays("2020_9ch")
ch5 = [str(c) for c in channels[:5]]
X5 = X[:, :5]
Xn, Yn = data.normalize(X5, Y, stats, ch5); Xn = np.nan_to_num(Xn, nan=0.0)
depths = np.asarray(DEPTHS, float)

# --- Is the holdout window itself sound? compare input & target statistics ---
print("=== window sanity (are the inputs/targets themselves abnormal?) ===")
for nm, sl in (("train days 0-292", slice(0, 293)), ("holdout days 293-365", slice(293, 366))):
    xb = X5[sl]; yb = Y[sl]
    fin = np.isfinite(yb)
    print(f"  {nm:<22} X mean {np.nanmean(xb):7.3f} sd {np.nanstd(xb):6.3f} | "
          f"Y mean {yb[fin].mean():6.3f} sd {yb[fin].std():6.3f} | finite {fin.mean():.3f}")

# --- per-depth RMSE, train vs holdout, model vs persistence ---
m = M.OceanModel(cin=5, D=256, Z=15); _ = m(tf.zeros([1, 5, 101, 241]))
m.load_weights("weights/model_2020.weights.h5")

def infer(idx):
    o = np.empty((len(idx), 15, 101, 241), np.float32)
    for k, i in enumerate(idx): o[k] = m(Xn[i:i+1], training=False)[0].numpy()
    return o * stats["y_std"] + stats["y_mean"]

tr = np.arange(0, 293); ho = np.arange(293, 366)
pt, ph = infer(tr), infer(ho)
per = Y[ho - 1]

print("\n=== per-depth RMSE (common mask, GLORYS) ===")
print(f"{'z(m)':>6} {'train':>8} {'HOLDOUT':>8} {'persist':>8}   {'holdout/train':>13}")
for d in range(15):
    ok = np.isfinite(Y[tr, d]) & np.isfinite(pt[:, d])
    okh = np.isfinite(Y[ho, d]) & np.isfinite(ph[:, d])
    r_t = np.sqrt(((pt[:, d] - Y[tr, d])[ok] ** 2).mean())
    r_h = np.sqrt(((ph[:, d] - Y[ho, d])[okh] ** 2).mean())
    r_p = np.sqrt(((per[:, d] - Y[ho, d])[okh] ** 2).mean())
    print(f"{depths[d]:6.0f} {r_t:8.3f} {r_h:8.3f} {r_p:8.3f}   {r_h/r_t:13.2f}x")

print("\n=== how much does GLORYS itself move day-to-day, per depth? ===")
for d in [0, 5, 10, 12, 14]:
    dY = Y[ho, d] - Y[ho - 1, d]
    f = np.isfinite(dY)
    print(f"  z={depths[d]:>5.0f} m : mean |daily change| = {np.abs(dY[f]).mean():.4f} C   sd = {dY[f].std():.4f}")
