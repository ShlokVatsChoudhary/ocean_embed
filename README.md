# OceanEmbed 🌊

### Satellite Embedding-Based Reconstruction of Subsurface Ocean Temperature

**OceanEmbed** is a deep-learning project developed for **Smart India Hackathon 2026 — Problem Statement 26066**. It aims to reconstruct subsurface ocean temperature from satellite-observed surface conditions, making subsurface ocean information easier to explore and analyse.

## Overview

Satellite observations capture the ocean surface, while understanding temperature beneath it is important for studying ocean dynamics and supporting marine and climate-related analysis.

OceanEmbed combines a deep-learning model with an interactive web application to visualise reconstructed temperature fields across the **North Indian Ocean**.

* **Region:** 5°N–30°N, 45°E–105°E
* **Spatial resolution:** 0.25° × 0.25°
* **Vertical range:** 0–1000 m
* **Output:** Temperature fields at 15 standard depths
* **Temporal resolution:** Daily model framework; the current demo exposes 1–7 January 2020

## Features

* **Subsurface temperature maps** across the supported depths.
* **Vertical profiles** to explore temperature variation with depth.
* **Model–reference comparison** against GLORYS reanalysis where data is available.
* **ARGO validation tools** for comparison with observational reference data.
* **Interactive visualisation** through a dashboard and a dedicated instrument-style console.
* **FastAPI backend** connecting the model, reference data, and frontend interfaces.

## Model Pipeline

The intended problem-statement pipeline uses seven surface variables: sea-surface temperature (SST), sea-surface salinity (SSS), sea-level anomaly (SLA), two wind components, and two current components.

The current integrated model uses **five input channels** — SST, SSS, SLA, UGOS, and VGOS — to predict temperature at 15 standard depths. Integration of the remaining wind inputs is still a limitation.

GLORYS reanalysis provides the model's training/reference temperature fields, while ARGO data is used for observational comparison. Validation results must be interpreted alongside the dataset's spatial and temporal resolution and training-period overlap.

## Tech Stack

| Component        | Technologies                                     |
| ---------------- | ------------------------------------------------ |
| Machine learning | TensorFlow, Keras, CNN encoder–decoder           |
| Backend          | Python, FastAPI, NumPy, xarray                   |
| Frontend         | React, Vite, JavaScript                          |
| Scientific data  | NetCDF, GLORYS, satellite-derived products, ARGO |
| Testing          | Pytest, frontend build checks                    |

## Project Structure

```text
ocean_embed/
├── backend/       # FastAPI application, data access and tests
├── frontend/
│   ├── dashboard/ # Main interactive dashboard
│   └── console/   # Instrument-style interface
├── model/
│   └── PS66-Ocean-Model/  # Model code, weights and samples
├── evaluation/    # Holdout and ARGO evaluation tools
├── scripts/       # Utility scripts
├── docs/          # Integration notes and figures
└── run.sh         # Local application launcher
```

## Getting Started

**Requirements:** Python 3.12+, Node.js/npm, and a Unix-like shell such as Linux, macOS, or WSL.

```bash
git clone https://github.com/ShlokVatsChoudhary/ocean_embed.git
cd ocean_embed

# Install backend dependencies
cd backend
python3 -m pip install -e .
cd ..

# Launch the application
chmod +x run.sh
./run.sh
```

The launcher starts the backend and both frontend interfaces.

| Service           | URL                        |
| ----------------- | -------------------------- |
| Main dashboard    | http://localhost:5173      |
| Console interface | http://localhost:5174      |
| API documentation | http://localhost:8000/docs |

To start only one interface, use `./run.sh --dashboard` or `./run.sh --console`. Stop the services with `./run.sh --stop`.

## Project Status

OceanEmbed includes an integrated web application, a TensorFlow inference adapter, bundled model weights and sample data, API tests, and evaluation tooling.

The current demo is limited to its bundled sample dates. Full-scale evaluation depends on the required datasets being available. The seven-variable problem-statement specification is not yet fully implemented, and validation results should not be interpreted as proof of operational forecasting skill.

---

**Developed for Smart India Hackathon 2026**
Problem Statement: **SIH26066** · Team: **Overfitters**
