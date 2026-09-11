import os
import math
import sqlite3
import uuid
from datetime import datetime

from flask import Flask, render_template, request, redirect, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from ml_prediction import get_ai_eco_insights

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    RealDictCursor = None

try:
    from supabase import create_client
except ImportError:
    create_client = None


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'ecotrack_local_development_key')

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}

# Emission & Tree Sequestration Constants (kg CO2)
EMISSION_FACTORS = {
    'petrol': 0.192,
    'diesel': 0.171,
    'ev': 0.053,
    'bike': 0.045,
    'elec': 0.82,
    'lpg': 42.5,
    'waste': 0.52,
}
TREE_SPECIES = {
    'Banyan': 22.0,
    'Neem': 20.0,
    'Mango': 15.0,
    'Teak': 18.0,
    'Oak': 21.7,
    'Bamboo': 12.0,
}

DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
SUPABASE_URL = os.getenv('SUPABASE_URL', '').strip()
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY', '').strip()
SUPABASE_BUCKET = os.getenv('SUPABASE_BUCKET', 'plantation-photos').strip()


def using_postgres():
    return bool(DATABASE_URL and psycopg2)


def get_db():
    """Use Supabase/PostgreSQL in production and SQLite locally."""
    if using_postgres():
        db_url = DATABASE_URL
        if 'sslmode=' not in db_url:
            separator = '&' if '?' in db_url else '?'
            db_url += f'{separator}sslmode=require'
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        return conn, True

    db_path = os.path.join(BASE_DIR, 'ecotrack.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn, False


def init_db():
    conn, is_postgres = get_db()
    c = conn.cursor()

    if is_postgres:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
                username VARCHAR(80) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS emissions (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                month_year VARCHAR(7) NOT NULL,
                elec_kwh DOUBLE PRECISION,
                trans_km DOUBLE PRECISION,
                trans_type VARCHAR(20),
                lpg_cyl DOUBLE PRECISION,
                waste_kg DOUBLE PRECISION,
                total_co2 DOUBLE PRECISION
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS plantations (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                species VARCHAR(50),
                qty INTEGER,
                date_planted VARCHAR(10),
                location VARCHAR(100),
                status VARCHAR(20),
                photo VARCHAR(500)
            )
        """)
        conn.commit()
    else:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password_hash TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS emissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                month_year TEXT,
                elec_kwh REAL,
                trans_km REAL,
                trans_type TEXT,
                lpg_cyl REAL,
                waste_kg REAL,
                total_co2 REAL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS plantations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                species TEXT,
                qty INTEGER,
                date_planted TEXT,
                location TEXT,
                status TEXT,
                photo TEXT
            )
        """)
        conn.commit()

    conn.close()


def query_db(sql, args=(), one=False, commit=False):
    conn, is_postgres = get_db()
    c = conn.cursor()
    if not is_postgres:
        sql = sql.replace('%s', '?')

    c.execute(sql, args)
    rows = c.fetchone() if one else c.fetchall()

    if commit:
        conn.commit()

    conn.close()

    if one:
        return dict(rows) if rows else None
    return [dict(row) for row in rows] if rows else []


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def upload_photo(file, user_id):
    """Upload to Supabase Storage in production, local disk during development."""
    if not file or not file.filename:
        return None

    if not allowed_file(file.filename):
        return None

    safe_name = secure_filename(file.filename)
    unique_name = f"{user_id}/{uuid.uuid4().hex}_{safe_name}"

    if SUPABASE_URL and SUPABASE_SERVICE_KEY and create_client:
        try:
            supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            content = file.read()
            supabase.storage.from_(SUPABASE_BUCKET).upload(
                unique_name,
                content,
                {'content-type': file.mimetype, 'upsert': 'true'}
            )
            public_url = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(unique_name)
            return public_url
        except Exception as exc:
            app.logger.exception('Supabase Storage upload failed: %s', exc)
            return None

    local_name = f"{uuid.uuid4().hex}_{safe_name}"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], local_name))
    return local_name


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = query_db(
            "SELECT * FROM users WHERE username = %s",
            (request.form['username'],),
            one=True,
        )
        if user and check_password_hash(user['password_hash'], request.form['password']):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect('/')
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')


@app.route('/register', methods=['POST'])
def register():
    try:
        username = request.form['username'].strip()
        password = request.form['password']
        if not username or not password:
            raise ValueError('Missing credentials')
        hash_pwd = generate_password_hash(password)
        query_db(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
            (username, hash_pwd),
            commit=True,
        )
        flash('Registered! Please login.', 'success')
    except Exception:
        flash('Username already exists or registration failed.', 'danger')
    return redirect('/login')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.route('/')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    uid = session['user_id']
    emissions = query_db(
        "SELECT * FROM emissions WHERE user_id = %s ORDER BY month_year ASC",
        (uid,),
    ) or []
    plantations = query_db(
        "SELECT * FROM plantations WHERE user_id = %s",
        (uid,),
    ) or []

    latest = emissions[-1] if emissions else None
    monthly_co2 = latest['total_co2'] if latest else 0.0
    annual_co2 = monthly_co2 * 12 if latest else 0.0
    trees_required = math.ceil(annual_co2 / 20.0) if annual_co2 > 0 else 0

    active_trees = sum(p['qty'] for p in plantations if p['status'] != 'Failed')
    total_trees = sum(p['qty'] for p in plantations)
    annual_offset = sum(
        p['qty'] * TREE_SPECIES.get(p['species'], 20.0)
        for p in plantations if p['status'] != 'Failed'
    )
    offset_pct = min(100.0, (annual_offset / annual_co2 * 100.0)) if annual_co2 > 0 else 0.0

    if monthly_co2 == 0:
        rating = {'label': 'No Data', 'color': '#9ca3af', 'badge': 'badge-gray', 'desc': 'No consumption recorded yet.', 'pct': 0}
    elif monthly_co2 < 150:
        rating = {'label': 'Very Low', 'color': '#10b981', 'badge': 'badge-green', 'desc': 'Excellent! Far below global per capita avg (390 kg/mo).', 'pct': min(25, (monthly_co2 / 150) * 25)}
    elif monthly_co2 <= 300:
        rating = {'label': 'Good', 'color': '#22c55e', 'badge': 'badge-green', 'desc': 'Sustainable level. Below global average threshold.', 'pct': 25 + ((monthly_co2 - 150) / 150) * 25}
    elif monthly_co2 <= 450:
        rating = {'label': 'Moderate', 'color': '#f59e0b', 'badge': 'badge-amber', 'desc': 'Average footprint matching global per capita baseline.', 'pct': 50 + ((monthly_co2 - 300) / 150) * 25}
    elif monthly_co2 <= 600:
        rating = {'label': 'High', 'color': '#f97316', 'badge': 'badge-orange', 'desc': 'High emission level. Above global benchmark target.', 'pct': 75 + ((monthly_co2 - 450) / 150) * 20}
    else:
        rating = {'label': 'Critical', 'color': '#ef4444', 'badge': 'badge-red', 'desc': 'Critical footprint! Urgent offset reduction recommended.', 'pct': min(100, 95 + ((monthly_co2 - 600) / 400) * 5)}

    chart_labels = [e['month_year'] for e in emissions]
    chart_vals = [e['total_co2'] for e in emissions]

    return render_template(
        'dashboard.html', latest=latest, monthly_co2=monthly_co2,
        annual_co2=annual_co2, trees_required=trees_required,
        active_trees=active_trees, total_trees=total_trees,
        annual_offset=annual_offset, offset_pct=offset_pct,
        rating=rating, chart_labels=chart_labels,
        chart_vals=chart_vals, page='dashboard'
    )


@app.route('/calculator', methods=['GET', 'POST'])
def calculator():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        try:
            e = float(request.form.get('elec', 0))
            t_km = float(request.form.get('trans_km', 0))
            t_type = request.form.get('trans_type', 'petrol')
            lpg = float(request.form.get('lpg', 0))
            w = float(request.form.get('waste', 0))
        except ValueError:
            flash('Please enter valid numeric values.', 'danger')
            return redirect('/calculator')

        if e < 0 or t_km < 0 or lpg < 0 or w < 0:
            flash('Values cannot be negative.', 'danger')
            return redirect('/calculator')

        total = (
            e * EMISSION_FACTORS['elec']
            + t_km * EMISSION_FACTORS.get(t_type, 0.192)
            + lpg * EMISSION_FACTORS['lpg']
            + w * EMISSION_FACTORS['waste']
        )
        m_yr = request.form.get('month_year', datetime.now().strftime('%Y-%m'))

        query_db(
            "INSERT INTO emissions (user_id, month_year, elec_kwh, trans_km, trans_type, lpg_cyl, waste_kg, total_co2) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (session['user_id'], m_yr, e, t_km, t_type, lpg, w, total),
            commit=True,
        )
        flash('Monthly CO2 emission record saved!', 'success')
        return redirect('/')

    return render_template('calculator.html', page='calc', month=datetime.now().strftime('%Y-%m'))


@app.route('/trees', methods=['GET', 'POST'])
def trees():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        species = request.form.get('species', 'Neem')
        try:
            qty = max(1, int(request.form.get('qty', 1)))
        except ValueError:
            qty = 1
        loc = request.form.get('location', 'Garden')
        status = request.form.get('status', 'Healthy')
        date_p = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))

        photo = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename:
                photo = upload_photo(file, session['user_id'])
                if not photo:
                    flash('Photo upload failed. Plantation record was not saved.', 'danger')
                    return redirect('/trees')

        query_db(
            "INSERT INTO plantations (user_id, species, qty, date_planted, location, status, photo) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (session['user_id'], species, qty, date_p, loc, status, photo),
            commit=True,
        )
        flash('Plantation logged!', 'success')
        return redirect('/trees')

    plantations = query_db(
        "SELECT * FROM plantations WHERE user_id = %s ORDER BY id DESC",
        (session['user_id'],),
    ) or []
    return render_template('trees.html', plantations=plantations, species=TREE_SPECIES, page='trees')


@app.route('/insights')
def insights():
    if 'user_id' not in session:
        return redirect('/login')
    emissions = query_db(
        "SELECT * FROM emissions WHERE user_id = %s ORDER BY month_year ASC",
        (session['user_id'],),
    ) or []
    ai_insights = get_ai_eco_insights(emissions)
    return render_template('insights.html', ai_insights=ai_insights, page='insights')


@app.route('/update-tree/<int:pid>', methods=['POST'])
def update_tree(pid):
    if 'user_id' not in session:
        return redirect('/login')
    query_db(
        "UPDATE plantations SET status = %s WHERE id = %s AND user_id = %s",
        (request.form['status'], pid, session['user_id']),
        commit=True,
    )
    return redirect('/trees')


@app.route('/impact')
def impact():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('impact.html', factors=EMISSION_FACTORS, species=TREE_SPECIES, page='impact')


@app.route('/health')
def health():
    return {'status': 'ok'}


init_db()


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.getenv('PORT', 5000)), debug=True)
