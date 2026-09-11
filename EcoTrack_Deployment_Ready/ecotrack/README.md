# EcoTrack – Carbon Footprint & Tree Plantation Tracker

EcoTrack is a lightweight Flask semester mini-project that helps users estimate household carbon emissions, view historical trends, generate AI/ML-based insights, estimate tree offsets, and record plantation activity with photo proof.

## Features

- User registration and login
- Monthly household carbon-footprint calculation
- Historical emissions dashboard
- AI Eco Insights using Linear Regression for a 3-month forecast
- Rule-based recommendations based on the largest emission source
- Tree offset estimation
- Plantation records and health/status updates
- Plantation photo upload
- Carbon impact meter

## Technology

- Python + Flask
- SQLite for local development
- PostgreSQL/Supabase for deployed data
- Supabase Storage for deployed plantation photos
- Scikit-learn + NumPy for prediction
- HTML, CSS and JavaScript
- Chart.js for dashboard charts
- Gunicorn for production serving

## Run locally

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run:

```bash
python app.py
```

Open `http://127.0.0.1:5000/`.

When `DATABASE_URL` is not set, EcoTrack automatically uses the local `ecotrack.db` SQLite database and stores uploaded photos in `static/uploads/`.

## Deploying

The production version is designed for a free Render web service connected to a Supabase project.

### Supabase setup

1. Create a Supabase project.
2. Create a Storage bucket named `plantation-photos` and make it public for this semester demo.
3. Copy the Postgres connection string from Supabase's Connect/database settings.
4. Copy the project URL and service-role key for server-side Storage uploads.
5. Add them as environment variables in Render. Never commit the service-role key to GitHub.

Required environment variables:

```text
SECRET_KEY
DATABASE_URL
SUPABASE_URL
SUPABASE_SERVICE_KEY
SUPABASE_BUCKET=plantation-photos
```

Render can deploy this repository using:

```text
Build command: pip install -r requirements.txt
Start command: gunicorn app:app
```

The included `render.yaml` contains these settings.

## Data persistence

Local SQLite files and local upload files are intentionally ignored by Git. In the deployed configuration, user records are stored in Supabase Postgres and plantation photos are stored in Supabase Storage instead of the Render server filesystem.

## ML methodology

EcoTrack uses Linear Regression as a simple and interpretable baseline. With at least two historical monthly records, the model maps month index to total monthly CO2 emissions and predicts the next three months. Predictions are estimates, not guaranteed outcomes.

## Core formulas

Monthly CO2:

```text
CO2 = (electricity × 0.82)
    + (transport distance × vehicle factor)
    + (LPG cylinders × 42.5)
    + (waste × 0.52)
```

Tree offset:

```text
Trees required = ceil(annual CO2 / tree sequestration rate)
```

## Important security note

Do not commit `.env`, database passwords, Supabase service-role keys, real user data, or private photos to GitHub.
