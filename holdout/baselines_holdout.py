import sys, os, numpy as np, tensorflow as tf
MODEL_DIR = "/Users/yogchhablani/Downloads/PS66-Ocean-Model-9ch"
sys.path.insert(0, MODEL_DIR); os.chdir(MODEL_DIR)
from src import data, baselines as B
from src import model as M
from src.config import DEPTHS

X, Y, stats, channels = data.load_arrays("2020_9ch")
ch5 = [str(c) for c in channels[:5]]
depths = np.asarray(DEPTHS, float); T = X.shape[0]
lo = T - T // 5                      # 293  first holdout day
times = np.arange(T).astype("timedelta64[D]") + np.datetime64("2020-01-01")
train_mask = np.zeros(T, bool); train_mask[:lo] = True

Xn, Yn = data.normalize(X[:, :5], Y, stats, ch5); Xn = np.nan_to_num(Xn, nan=0.0)
m = M.OceanModel(cin=5, D=256, Z=15); _ = m(tf.zeros([1, 5, 101, 241]))
m.load_weights("weights/model_2020.weights.h5")
P = np.empty_like(Y[lo:])
for k, i in enumerate(range(lo, T)):
    P[k] = m(Xn[i:i+1], training=False)[0].numpy() * stats["y_std"] + stats["y_mean"]
TRUE = Y[lo:]

zz = depths[:, None, None]
def mask3(sel): return np.broadcast_to(sel, TRUE.shape)
def rep(nm, P_, TRUE_=None):
    Tt = TRUE if TRUE_ is None else TRUE_
    ok = np.isfinite(P_) & np.isfinite(Tt)
    out = []
    for sel in (np.ones_like(ok, bool), mask3(zz >= 50), mask3((zz >= 50) & (zz <= 200))):
        s = ok & sel
        out.append(np.sqrt(((P_ - Tt)[s] ** 2).mean()))
    print(f"{nm:<38} {out[0]:7.3f} {out[1]:7.3f} {out[2]:7.3f}")
    return out[0]

print("=== GENUINE TEMPORAL HOLDOUT (last 73 days of 2020; never trained on) vs GLORYS ===")
print(f"{'method':<38} {'all':>7} {'>=50m':>7} {'therm':>7}")
rep("OceanEmbed (surface -> subsurface)", P)

pp, tt = B.persistence(Y)                       # aligned to t=1..T-1
rep("persistence (prev. day: NOT obtainable)", pp[lo-1:], tt[lo-1:])

clim = B.fit_climatology(Y, times, train_mask)
rep("climatology (built from train days)", B.predict_climatology(clim, times)[lo:])

pred_fn = B.sst_to_T_mlp(X[:, :5], Y, train_mask, array_channels=ch5)
rep("SST+SLS -> T regression (operational)", pred_fn(np.arange(lo, T)))
