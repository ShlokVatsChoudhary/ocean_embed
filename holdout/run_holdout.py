"""Genuine temporal holdout: evaluate the SHIPPED weights on days the model never trained on.

run_day3.py splits 366 days as  train = 0..292   val = 293..365 (T // 5 = 73 days).
The published weights are the best-val-loss weights from that run, so days 293-365 are a
real, never-trained-on holdout.  We score both windows against GLORYS to prove the split
is genuine (train RMSE must be lower than holdout RMSE) and to report honest skill.
"""
import sys, numpy as np, tensorflow as tf
MODEL_DIR = "/Users/yogchhablani/Downloads/PS66-Ocean-Model-9ch"
sys.path.insert(0, MODEL_DIR)
import os; os.chdir(MODEL_DIR)
from src import data
from src import model as M
from src.config import DEPTHS

TAG = "2020_9ch"
N_TRAIN = 293            # 366 - 366//5
W = 73                   # matched sample from the training window

X, Y, stats, channels = data.load_arrays(TAG)
X5 = X[:, :5]                                     # the 5ch model consumes the first 5 channels
ch5 = [str(c) for c in channels[:5]]
assert ch5 == ["sst", "sss", "sla", "ugos", "vgos"], ch5

Xn, Yn = data.normalize(X5, Y, stats, ch5)
# normalise() may keep NaNs on land; sanitise so convolutions do not smear them (as in the backend fix)
Xn = np.nan_to_num(Xn, nan=0.0)

m = M.OceanModel(cin=5, D=256, Z=Y.shape[1])
_ = m(tf.zeros([1, 5, 101, 241]))                 # force a real build
m.load_weights("weights/model_2020.weights.h5")
print(f"weights loaded; params = {m.count_params():,}")

depths = np.asarray(DEPTHS, float)
t = Y.shape[0]
assert (t, Y.shape[1]) == (366, 15), (t, Y.shape[1])
n_val = t // 5
val_idx = np.arange(t - n_val, t)
train_idx = np.arange(0, n_val * 0 + N_TRAIN)

rng = np.random.default_rng(0)
train_sample = np.sort(rng.choice(train_idx, size=min(W, len(train_idx)), replace=False))

def infer(idx):
    out = np.empty((len(idx),) + Y.shape[1:], np.float32)
    for k, i in enumerate(idx):
        out[k] = m(Xn[i:i + 1], training=False)[0].numpy()
    return out * stats["y_std"] + stats["y_mean"]

def bands(pred, truth, idx):
    """Common mask: cells finite in BOTH the model prediction and GLORYS at that depth."""
    yt = truth[idx]
    ocean = np.isfinite(yt[0]) & np.isfinite(pred[0])          # surface ocean mask
    res = {}
    for name, ok in (
        ("all",  np.isfinite(yt) & np.isfinite(pred)),
        (">=50m", np.isfinite(yt) & np.isfinite(pred) & (depths >= 50)[:, None, None]),
        ("therm", np.isfinite(yt) & np.isfinite(pred) & ((depths >= 50) & (depths <= 200))[:, None, None]),
    ):
        d = (pred - yt)[ok]
        res[name] = (float(np.sqrt((d ** 2).mean())), int(ok.sum()))
    return res, int(ocean.sum())

print("\n--- GLORYS skill, common mask ---")
print(f"{'window':<26} {'all':>7} {'>=50m':>7} {'therm':>7}   n_cells")
rows = {}
for name, idx in (("TRAIN days 0-292 (in-sample)", train_sample),
                  ("HOLDOUT days 293-365", val_idx)):
    pred = infer(idx)
    b, nc = bands(pred, Y, idx)
    rows[name] = b
    print(f"{name:<26} {b['all'][0]:7.3f} {b['>=50m'][0]:7.3f} {b['therm'][0]:7.3f}   {nc}")

# persistence baseline: previous GLORYS day, scored on the identical holdout mask
pers = Y[val_idx - 1]
bp, _ = bands(pers, Y, val_idx)
print(f"{'persistence (prev. day)':<26} {bp['all'][0]:7.3f} {bp['>=50m'][0]:7.3f} {bp['therm'][0]:7.3f}   (holdout)")

tr = rows["TRAIN days 0-292 (in-sample)"]["all"][0]
ho = rows["HOLDOUT days 293-365"]["all"][0]
print(f"\nholdout penalty: {ho - tr:+.3f} C  ({(ho / tr - 1) * 100:+.1f}%)")
print("VERDICT:", "genuine holdout confirmed (holdout harder than train)" if ho > tr
      else "WARNING: holdout not harder than train - split may not be honest")
