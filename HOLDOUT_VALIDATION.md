# Genuine temporal holdout — the 2021 download is NOT needed

## Discovery
`src/run_day3.py` splits the 366 days of 2020 as:

```python
n_val = max(5, T // 5)              # 366 // 5 = 73
val_idx   = np.arange(T - n_val, T) # days 293-365  (20 Oct – 31 Dec 2020)
train_idx = np.arange(0, T - n_val) # days   0-292  (1 Jan – 19 Oct 2020)
```

The published weights (`weights/model_2020.weights.h5`, sha256 `0eeb3ea6…` — **byte-identical to the
weights the backend serves**) are the *best-val-loss* weights from that run. So days 293–365 were
never trained on. Together with the full-year arrays and full-year ARGO that ship in
`~/Downloads/PS66-Ocean-Model-9ch`, this is a real out-of-sample evaluation at **zero download cost**.

Caveat: the holdout was used for early stopping / model selection, so it is a *validation* set, not a
fully pristine test set. No gradient step ever used it.

## Result 1 — vs GLORYS (the training target)

| method | all | ≥50 m | thermocline |
|---|---|---|---|
| **OceanEmbed** | **0.769** | **0.875** | **1.079** |
| persistence (prev. day) | **0.138** | 0.153 | 0.193 |
| climatology (from train days) | 1.458 | 1.666 | 2.108 |
| SST+SLS→T regression (operational) | 0.906 | 0.950 | 1.189 |

In-sample the model scores **0.353**. On the holdout it scores **0.769** — a **2.2× degradation**,
worst in the thermocline (2.7× at 75–125 m).

**Against GLORYS the model loses to persistence at every single depth, in-sample and out-of-sample.**

Why: GLORYS barely moves day to day. Mean |daily change| is **0.086 °C at the surface**, 0.11 °C at
50 m, 0.016 °C at 1000 m. "Assume no change" is therefore an almost perfect predictor of this target.

## Result 2 — vs independent ARGO 2020

| method | holdout all | ≥50 m | therm | | train all | ≥50 m | therm |
|---|---|---|---|---|---|---|---|
| OceanEmbed | **1.030** | **1.210** | **1.518** | | 1.017 | 1.147 | 1.438 |
| persistence (prev. GLORYS day) | 1.033 | 1.231 | 1.548 | | 1.070 | 1.195 | 1.498 |
| climatology (from train days) | 1.308 | 1.543 | 1.951 | | 1.072 | 1.197 | 1.500 |

Against independent observations the model **ties persistence** (1.030 vs 1.033, +0.3 %) and is
marginally ahead in the bands (+1.7 % at ≥50 m, +1.9 % in the thermocline).

## The two results disagree — and the reason matters

The same model, the same window, two targets, opposite verdicts:

| | GLORYS | ARGO |
|---|---|---|
| model | 0.769 | 1.030 |
| persistence | **0.138** | 1.033 |
| verdict | persistence wins 5.6× | dead heat |

ARGO is a 10-day composite on a 1° grid upsampled to 0.25°. Its own representativeness error creates
an **error floor** that inflates every method to ~1.0 °C and swamps the differences. GLORYS is a
smooth reanalysis, so its persistence baseline is artificially — and unrealistically — strong.

**Neither target is a clean arbiter.** The GLORYS comparison is contaminated (it is the training
target) but sensitive; the ARGO comparison is independent but noisy.

## What is actually safe to claim

1. The model **beats climatology by 21 %** out-of-sample against independent ARGO (1.030 vs 1.308).
2. The model **beats an operational SST→T regression by 15 %** (0.769 vs 0.906 vs GLORYS).
3. The model **matches persistence** against independent ARGO (+0.3 % all-depth).
4. The model **loses badly to persistence** against GLORYS (5.6×), because GLORYS is temporally
   smooth and persistence is a reanalysis-derived baseline no satellite-only system could compute.
5. Out-of-sample degradation vs independent ARGO is only **1.3 %** — the model generalises in time
   against real observations, even though it degrades 2.2× against the reanalysis.

Claim 4 must be disclosed. Claim 5 is the genuinely good news and is not currently on the deck.
