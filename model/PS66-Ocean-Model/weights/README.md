# Trained weights

| File | Size | Description |
|---|---|---|
| `model_2020.weights.h5` | 6.7 MB | Trained on the full year 2020 (366 days), 1,643,288 parameters |

This is the model referenced throughout `README.md` and `STATUS.md`. It is small
enough to live in git (GitHub's limit is 100 MB per file).

## Loading it

```python
import sys; sys.path.insert(0, ".")
import numpy as np, tensorflow as tf
from src import config, data, model as M

X, Y, stats, ch = data.load_arrays("2020")          # falls back to samples/
Xn, _ = data.normalize(X, Y, stats, ch)

m = M.OceanModel(cin=X.shape[1], D=256, Z=Y.shape[1])
_ = m(tf.zeros([1, X.shape[1], X.shape[2], X.shape[3]]))   # build
m.load_weights(config.ROOT / "weights" / "model_2020.weights.h5")

p, z = m(np.nan_to_num(Xn[:4], nan=0.0).astype("float32"), training=False)
pred = p.numpy() * (stats["y_std"] + 1e-6) + stats["y_mean"]  # de-normalise
```

Or just run the bundled demo, which does all of the above:

```bash
python quickstart.py
```

## Architecture requirement

The weights are *values only* — they carry no structure. You must build
`M.OceanModel(cin=5, D=256, Z=15)` first, exactly as above, or `load_weights`
will fail. See `ARCHITECTURE.md`.

## Retraining

`run_day3.py` writes new weights to `checkpoints/model_<tag>.weights.h5`
(that folder is gitignored). To publish a new one, copy it here and update
the tag in `README.md`.

> If a checkpoint ever exceeds 100 MB, attach it to a GitHub Release or use
> [Git LFS](https://git-lfs.com/) instead of committing it.
