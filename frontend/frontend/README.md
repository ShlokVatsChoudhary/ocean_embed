# OceanEmbed — frontend

Subsurface temperature explorer for the North Indian Ocean (5°N–30°N, 45°E–105°E),
built with React + Vite. Reconstructs daily 0.25° temperature fields from 0–1000 m
and validates them against GLORYS reanalysis and ARGO float profiles.

## Getting started

```bash
npm install
npm run dev
```

The app opens at `http://localhost:5173` by default.

## Environment variables

Copy `.env.example` to `.env` and set your backend URL if you have one running:

```bash
cp .env.example .env
```

Leave `VITE_API_BASE` empty (or skip the `.env` file entirely) to use the
built-in local mock data — no backend required to run the UI.

## Scripts

- `npm run dev` — start the local dev server
- `npm run build` — production build to `dist/`
- `npm run preview` — preview the production build locally
- `npm run lint` — run oxlint

## Structure

```
src/
  api/          data-fetching layer (mock + optional backend)
  components/   shared UI: Hero (front page), map, charts, controls
  views/        Explore / Analyze / Validate tabs
  App.jsx       app shell + routing between the front page and dashboard
  index.css     design tokens and styles
```
