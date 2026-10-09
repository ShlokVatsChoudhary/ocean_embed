# OceanEmbed 🌊

### Satellite Embedding-Based Reconstruction of Subsurface Ocean Temperature

**OceanEmbed** is a deep-learning project developed for **Smart India Hackathon 2026 — Problem Statement 26066**. It aims to reconstruct subsurface ocean temperature from satellite-observed surface conditions, making subsurface ocean information easier to explore and analyse.

## Overview

OceanEmbed combines satellite-derived ocean observations with a deep-learning model and an interactive web application to visualise reconstructed temperature fields across the **North Indian Ocean**.

* **Region:** 5°N–30°N, 45°E–105°E
* **Spatial resolution:** 0.25° × 0.25°
* **Vertical range:** 0–1000 m
* **Output:** Temperature fields at 15 standard depths
* **Temporal resolution:** Daily

## Features

* **Subsurface temperature maps** across multiple depths.
* **Vertical profiles** to explore temperature variation with depth.
* **Model–reference comparison** against GLORYS reanalysis.
* **ARGO observation comparison** for model evaluation.
* **Interactive visualisation** through a web dashboard and instrument-style console.
* **FastAPI backend** connecting model inference, scientific datasets, and frontend interfaces.

## Model Pipeline

The seven-channel input specification covers the key surface variables required by the problem statement:

| Input | Variable                           |
| ----- | ---------------------------------- |
| 1     | Sea Surface Temperature (SST)      |
| 2     | Sea Surface Salinity (SSS)         |
| 3     | Sea Level Anomaly (SLA)            |
| 4     | Zonal Wind Component (U-wind)      |
| 5     | Meridional Wind Component (V-wind) |
| 6     | Zonal Ocean Current (UGOS)         |
| 7     | Meridional Ocean Current (VGOS)    |

A CNN encoder–decoder processes these surface inputs to reconstruct temperature at 15 standard depths: 0, 5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 300, 500, 700, and 1000 m.

GLORYS reanalysis provides reference temperature fields for model training and comparison, while ARGO observations support evaluation against in-situ measurements.

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

To start a single interface, use `./run.sh --dashboard` or `./run.sh --console`. Stop the services with `./run.sh --stop`.

## Project Status

OceanEmbed brings together deep-learning-based temperature reconstruction, an interactive visualisation platform, reference-data comparisons, and evaluation tooling. The application supports exploration of reconstructed subsurface temperature fields across the North Indian Ocean.

Model performance and observational validation should be interpreted in the context of data coverage, spatial and temporal resolution, and the independence of evaluation periods.

---

**Developed for Smart India Hackathon 2026**
Problem Statement: **SIH26066** · Team: **Overfitters**
