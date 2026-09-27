"""Day-3 driver: train the encoder/decoder on the available window and score it.

Prototype on the current (1-month) arrays first. Point it at a year's arrays
later -- no code changes needed.

Usage:
    python run_day3.py 2020-01-01_2020-01-31
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import config, data, metrics as ev, model as M


def collect_preds(model, ds):
    preds = []
    for xb, _yb, _mb in ds:
        p, _z = model(xb, training=False)
        preds.append(p.numpy())
    return np.concatenate(preds, axis=0)


def main(tag: str, epochs: int = 120, batch: int = 4, seed: int = 0):
    tf = M.tf
    tf.random.set_seed(seed)
    print(f"\n=== Day 3: train encoder/decoder on tag={tag} ===\n")

    X, Y, stats, channels = data.load_arrays(tag)
    Xn, Yn = data.normalize(X, Y, stats, channels)
    T = X.shape[0]
    print(f"X {X.shape}  Y {Y.shape}  channels={channels}")

    # temporal split
    n_val = max(5, T // 5)
    val_idx = np.arange(T - n_val, T)
    train_idx = np.arange(0, T - n_val)
    print(f"train days={len(train_idx)}  val days={len(val_idx)}")

    ds_tr = data.make_dataset(Xn, Yn, train_idx, batch=batch, shuffle=True)
    ds_va = data.make_dataset(Xn, Yn, val_idx, batch=batch, shuffle=False)

    model = M.OceanModel(cin=X.shape[1], D=256, Z=Y.shape[1])
    # NOTE: do NOT call model.build() -- on subclassed models it marks the model
    # built without creating weights. Force a real forward pass instead.
    _ = model(tf.zeros([1, X.shape[1], X.shape[2], X.shape[3]]))
    print(f"params: {model.count_params():,}")

    # ---- explicit training loop (Keras 3 fit() mishandles a custom train_step's
    # loss, so we drive GradientTape ourselves for correct logging/early stop) ----
    opt = tf.keras.optimizers.Adam(1e-3)
    best_loss, best_w, wait, patience = np.inf, None, 0, 30
    hist = {"loss": [], "val_loss": []}
    for epoch in range(epochs):
        tl, nt = 0.0, 0
        for xb, yb, mb in ds_tr:
            with tf.GradientTape() as tape:
                pred, _ = model(xb, training=True)
                loss = model.masked_loss(yb, pred, mb)
            grads = tape.gradient(loss, model.trainable_variables)
            opt.apply_gradients(zip(grads, model.trainable_variables))
            tl += float(loss); nt += 1
        vl, nv = 0.0, 0
        for xb, yb, mb in ds_va:
            pred, _ = model(xb, training=False)
            vl += float(model.masked_loss(yb, pred, mb)); nv += 1
        tl /= max(nt, 1); vl /= max(nv, 1)
        hist["loss"].append(tl); hist["val_loss"].append(vl)
        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"  epoch {epoch+1:3d}  train {tl:.4f}  val {vl:.4f}")
        if vl < best_loss - 1e-5:
            best_loss, wait = vl, 0
            best_w = [np.array(w) for w in model.get_weights()]
        else:
            wait += 1
            if wait >= patience:
                print(f"  early stop at epoch {epoch+1}")
                break
    if best_w is not None:
        model.set_weights(best_w)
        print(f"  restored best weights (val loss {best_loss:.4f})")

    # ---- evaluate in physical units ----
    predn = collect_preds(model, ds_va)                       # normalized
    pred = predn * (stats["y_std"] + 1e-6) + stats["y_mean"]
    true = Y[val_idx]
    # mask land
    pred = np.where(np.isfinite(true), pred, np.nan)

    m = ev.per_depth_metrics(pred, true)
    ev.print_table(m, "model (Encoder-Decoder)")
    s = ev.overall_score(m)

    # ---- honest headline: common mask + depth bands, and the same numbers
    # for the strongest baseline (persistence from the last training day) ----
    last_train = (T - n_val) - 1
    pers = np.repeat(Y[last_train][None], len(val_idx), axis=0)
    print("\n--- honest headline (common mask: cells valid at every depth) ---")
    mc = ev.print_headline(pred, true, "model", common=True)
    pc = ev.print_headline(pers, true, "persistence", common=True)
    win = ev.wins_vs(pc, mc)
    won = [config.DEPTHS[i] for i in range(len(config.DEPTHS)) if win[i]]
    lost = [config.DEPTHS[i] for i in range(len(config.DEPTHS)) if not win[i]]
    print(f"  model beats persistence at: {won}")
    print(f"  persistence wins at:        {lost}")

    # ---- compare to saved baselines if present ----
    bpath = config.DATA_PROC / f"baselines_{tag}.npz"
    if bpath.exists():
        b = np.load(bpath)
        print("\n--- vs baselines (mean RMSE) ---")
        print(f"  {'model':12s} RMSE={s['rmse_mean']:.3f}  Corr={s['corr_mean']:.3f}")
        for name in ("persistence", "climatology", "sst_mlp"):
            k = f"{name}_rmse"
            if k in b:
                print(f"  {name:12s} RMSE={float(np.nanmean(b[k])):.3f}  "
                      f"Corr={float(np.nanmean(b[name + '_corr'])):.3f}")

    # ---- RMSE-vs-depth plot ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5.5, 6))
    ax.plot(m["rmse"], m["depth"], "o-", label="Encoder-Decoder")
    if bpath.exists():
        b = np.load(bpath)
        for name in ("persistence", "climatology", "sst_mlp"):
            k = f"{name}_rmse"
            if k in b:
                ax.plot(b[k], b["depth"], "--", label=name)
    ax.invert_yaxis()
    ax.set_xlabel("RMSE (deg C)")
    ax.set_ylabel("Depth (m)")
    ax.set_title(f"Model vs baselines ({tag})")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fname = config.FIGURES / f"model_rmse_{tag}.png"
    fig.savefig(fname, dpi=140, bbox_inches="tight")
    print(f"\n[fig] {fname}")
    model.save_weights(config.CHECKPOINTS / f"model_{tag}.weights.h5")
    print(f"[ckpt] {config.CHECKPOINTS / f'model_{tag}.weights.h5'}")
    print("=== Day 3 complete ===\n")
    return m, hist


if __name__ == "__main__":
    tg = sys.argv[1] if len(sys.argv) > 1 else "2020-01-01_2020-01-31"
    ep = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    main(tg, epochs=ep)
