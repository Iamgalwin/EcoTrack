import datetime
import numpy as np
from sklearn.linear_model import LinearRegression

# Standard emission factors used in EcoTrack (kg CO2)
EMISSION_FACTORS = {
    'petrol': 0.192,
    'diesel': 0.171,
    'ev': 0.053,
    'bike': 0.045,
    'elec': 0.82,
    'lpg': 42.5,
    'waste': 0.52
}

def analyze_emissions(emissions_data):
    """
    Analyzes historical emission records to identify the largest emission source
    and overall emission trend.
    """
    if not emissions_data:
        return {
            'has_data': False,
            'largest_source': None,
            'largest_pct': 0,
            'breakdown': {},
            'trend': 'No Data',
            'summary_text': 'No historical emission data available yet.'
        }

    # Sum up emissions per category across all records
    elec_co2 = sum(float(e.get('elec_kwh', 0) or 0) * EMISSION_FACTORS['elec'] for e in emissions_data)
    trans_co2 = sum(
        float(e.get('trans_km', 0) or 0) * EMISSION_FACTORS.get(e.get('trans_type', 'petrol'), 0.192)
        for e in emissions_data
    )
    lpg_co2 = sum(float(e.get('lpg_cyl', 0) or 0) * EMISSION_FACTORS['lpg'] for e in emissions_data)
    waste_co2 = sum(float(e.get('waste_kg', 0) or 0) * EMISSION_FACTORS['waste'] for e in emissions_data)

    categories = {
        'Electricity': elec_co2,
        'Transportation': trans_co2,
        'LPG': lpg_co2,
        'Waste': waste_co2
    }

    total_sum = sum(categories.values())

    if total_sum > 0:
        largest_source = max(categories, key=categories.get)
        largest_pct = round((categories[largest_source] / total_sum) * 100)
    else:
        largest_source = 'Electricity'
        largest_pct = 0

    # Trend calculation using linear slope if >= 2 points
    totals = [float(e.get('total_co2', 0) or 0) for e in emissions_data]
    if len(totals) >= 2:
        x = np.arange(len(totals)).reshape(-1, 1)
        y = np.array(totals)
        model = LinearRegression()
        model.fit(x, y)
        slope = float(model.coef_[0])
        avg_val = np.mean(y) if np.mean(y) > 0 else 1.0
        
        # Slope relative to average
        relative_slope = slope / avg_val
        if relative_slope > 0.03:
            trend = 'Increasing'
        elif relative_slope < -0.03:
            trend = 'Decreasing'
        else:
            trend = 'Relatively stable'
    else:
        trend = 'Relatively stable'

    summary_text = (
        f"{largest_source} is your largest emission source, contributing {largest_pct}% "
        f"of your total estimated emissions. Your overall emissions trend is {trend.lower()}."
    )

    return {
        'has_data': True,
        'largest_source': largest_source,
        'largest_pct': largest_pct,
        'breakdown': {k: round(v, 2) for k, v in categories.items()},
        'trend': trend,
        'summary_text': summary_text
    }


def predict_future_emissions(emissions_data):
    """
    Uses Scikit-Learn Linear Regression to predict emissions for the next 3 months.
    Requires at least 2 historical data points.
    """
    if not emissions_data or len(emissions_data) < 2:
        return {
            'can_predict': False,
            'message': 'More historical data is required to generate a reliable prediction.',
            'pred_labels': [],
            'pred_vals': [],
            'pct_change': 0,
            'summary': 'More historical data is required to generate a reliable prediction.'
        }

    # Extract historical monthly values and labels
    hist_labels = [e.get('month_year', f"Mo-{i+1}") for i, e in enumerate(emissions_data)]
    y_train = np.array([float(e.get('total_co2', 0) or 0) for e in emissions_data])
    x_train = np.arange(len(y_train)).reshape(-1, 1)

    # Train simple Linear Regression model
    model = LinearRegression()
    model.fit(x_train, y_train)

    # Predict for next 3 months
    n_hist = len(y_train)
    x_future = np.array([[n_hist], [n_hist + 1], [n_hist + 2]])
    y_future = model.predict(x_future)

    # Ensure non-negative predictions
    y_future_clean = [round(max(0.0, float(val)), 1) for val in y_future]

    # Generate future month labels (e.g., 2026-09, 2026-10, 2026-11)
    last_label = hist_labels[-1]
    future_labels = []
    try:
        dt = datetime.datetime.strptime(last_label, "%Y-%m")
        for i in range(1, 4):
            # Add i months
            month = dt.month - 1 + i
            year = dt.year + month // 12
            month = month % 12 + 1
            future_labels.append(f"{year:04d}-{month:02d}")
    except Exception:
        for i in range(1, 4):
            future_labels.append(f"+{i} Month")

    # Percentage change calculation: compare last actual to 3rd predicted month
    last_actual = float(y_train[-1]) if y_train[-1] > 0 else 1.0
    final_pred = float(y_future_clean[-1])
    pct_change = round(float(((final_pred - last_actual) / last_actual) * 100), 1)

    if pct_change > 0:
        direction_text = f"increase by approximately {abs(pct_change)}%"
    elif pct_change < 0:
        direction_text = f"decrease by approximately {abs(pct_change)}%"
    else:
        direction_text = "remain relatively stable"

    summary = f"Your monthly carbon emissions are predicted to {direction_text} over the next 3 months."

    return {
        'can_predict': True,
        'message': None,
        'hist_labels': hist_labels,
        'hist_vals': [round(float(v), 1) for v in y_train],
        'pred_labels': future_labels,
        'pred_vals': y_future_clean,
        'pct_change': pct_change,
        'summary': summary,
        'disclaimer': 'Predictions are linear estimates based on historical trends and are not guaranteed results.'
    }


def generate_recommendations(largest_source, trend):
    """
    Generates actionable, prioritized eco-recommendations based on largest emission category.
    """
    recs_map = {
        'Electricity': [
            "Reduce unnecessary electricity usage by switching off unused lighting and devices.",
            "Improve appliance efficiency by upgrading to energy-efficient models and LED bulbs.",
            "Avoid unnecessary standby consumption by turning off appliances at the wall socket."
        ],
        'Transportation': [
            "Reduce unnecessary vehicle trips by planning and combining daily errands.",
            "Use public transportation or carpool whenever traveling regular routes.",
            "Walk or cycle for short distances to replace car or motor bike trips."
        ],
        'LPG': [
            "Improve cooking efficiency by placing lids on pots and using pressure cookers.",
            "Reduce unnecessary LPG consumption by optimizing flame size and meal prep."
        ],
        'Waste': [
            "Reduce household waste by avoiding single-use plastics and excess packaging.",
            "Reuse materials and separate recyclable waste items into paper, plastic, and metal.",
            "Compost suitable organic kitchen waste to keep organic matter out of landfills."
        ]
    }

    selected_recs = recs_map.get(largest_source, recs_map['Electricity'])

    # Add trend-aware recommendation if emissions are increasing
    if trend == 'Increasing':
        selected_recs = list(selected_recs)
        selected_recs[0] = selected_recs[0] + " (Emissions are trending upward—prioritize this step)."

    return selected_recs


def get_ai_eco_insights(emissions_data):
    """
    Full pipeline function that compiles usage analysis, prediction model output,
    and personalized recommendations for the dashboard UI.
    """
    analysis = analyze_emissions(emissions_data)
    prediction = predict_future_emissions(emissions_data)
    recommendations = generate_recommendations(analysis['largest_source'], analysis['trend'])

    return {
        'analysis': analysis,
        'prediction': prediction,
        'recommendations': recommendations
    }
