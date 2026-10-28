from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import psycopg2
from psycopg2 import extras
import math

app = Flask(__name__)
app.secret_key = "prohands_ultra_key_2026"

```python
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "prohands_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        cursor_factory=extras.DictCursor,
    )
```
def calculate_distance_and_eta(lat1, lon1, lat2, lon2):
    if not lat1 or not lon1 or not lat2 or not lon2:
        return "0.0 km", "N/A"
    R = 6371
    dlat = math.radians(float(lat2) - float(lat1))
    dlon = math.radians(float(lon2) - float(lon1))
    a = math.sin(dlat/2)**2 + math.cos(math.radians(float(lat1))) * math.cos(math.radians(float(lat2))) * math.sin(dlon/2)**2
    geodesic_km = round(2 * R * math.asin(math.sqrt(a)), 2)
    driving_km = round(geodesic_km * 1.3, 1)
    avg_speed_kmh = 30
    travel_hours = driving_km / avg_speed_kmh
    minutes = max(1, int(round(travel_hours * 60)))
    return f"{driving_km} km", f"{minutes} mins"

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        idnt = request.form.get('email').strip().lower()
        entered_password = request.form.get('password')
        role = request.form.get('role')
        
        conn = get_db_connection(); cur = conn.cursor()
        if role == 'worker':
            cur.execute("SELECT id FROM workers WHERE (LOWER(email) = %s OR LOWER(name) = %s) AND password = %s", (idnt, idnt, entered_password))
            w = cur.fetchone()
            if w:
                session['worker_id'] = w['id']
                cur.close(); conn.close()
                return redirect(url_for('worker_dashboard', worker_id=w['id']))
        else:
            cur.execute("SELECT id, email FROM users WHERE LOWER(email) = %s AND password = %s", (idnt, entered_password))
            u = cur.fetchone()
            if u:
                session['user_id'] = u['id']
                session['user_email'] = u['email']
                cur.close(); conn.close()
                return redirect(url_for('user_home'))
                
        cur.close(); conn.close()
        return "Invalid credentials."
    return render_template('login.html')

@app.route('/register-user', methods=['POST'])
def register_user():
    name = request.form.get('name')
    email = request.form.get('email').strip().lower()
    phone = request.form.get('phone')
    password = request.form.get('password')
    
    live_lat = request.form.get('lat', '').strip()
    live_lon = request.form.get('lon', '').strip()
    manual_lat = request.form.get('manual_lat', '').strip()
    manual_lon = request.form.get('manual_lon', '').strip()
    
    final_lat = live_lat if live_lat else manual_lat
    final_lon = live_lon if live_lon else manual_lon
    
    lat = float(final_lat) if final_lat else 12.9716
    lon = float(final_lon) if final_lon else 77.5946
    
    conn = get_db_connection(); cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO users (name, email, phone, password, latitude, longitude) 
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """, (name, email, phone, password, lat, lon))
        user_id = cur.fetchone()[0]
        conn.commit()
        session['user_id'] = user_id
        session['user_email'] = email
        return redirect(url_for('user_home'))
    except Exception as e:
        conn.rollback()
        return f"Error during user registration: {e}"
    finally:
        cur.close(); conn.close()

@app.route('/worker-setup')
def worker_setup():
    return render_template('worker_setup.html')

@app.route('/create-profile', methods=['POST'])
def create_profile():
    name = request.form.get('name')
    email = request.form.get('email').strip().lower()
    phone = request.form.get('phone')
    qual = request.form.get('qualification')
    job = request.form.get('job_expert')
    wage = request.form.get('daily_wage')
    text_town = request.form.get('town')
    password = request.form.get('password')
    
    live_lat = request.form.get('lat', '').strip()
    live_lon = request.form.get('lon', '').strip()
    manual_lat = request.form.get('manual_lat', '').strip()
    manual_lon = request.form.get('manual_lon', '').strip()
    
    final_lat = live_lat if live_lat else manual_lat
    final_lon = live_lon if live_lon else manual_lon
    
    lat = float(final_lat) if final_lat else 12.9224
    lon = float(final_lon) if final_lon else 77.4981

    conn = get_db_connection(); cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO workers (name, email, phone_number, qualification, job_expert, 
            latitude, longitude, rating, review_count, town_name, daily_wage, password)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 0.0, 0, %s, %s, %s) RETURNING id
        """, (name, email, phone, qual, job, lat, lon, text_town, wage, password))
        worker_id = cur.fetchone()[0]
        conn.commit()
        session['worker_id'] = worker_id
        return redirect(url_for('worker_dashboard', worker_id=worker_id))
    except Exception as e:
        conn.rollback()
        return f"Registration Error: {e}"
    finally:
        cur.close(); conn.close()

@app.route('/update-location', methods=['POST'])
def update_location():
    data = request.get_json()
    booking_id = data.get('booking_id')
    lat = data.get('lat')
    lon = data.get('lon')
    
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("""
        UPDATE bookings 
        SET current_worker_lat = %s, current_worker_lon = %s 
        WHERE id = %s
    """, (lat, lon, booking_id))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"status": "success", "message": "Location updated"})

@app.route('/stream-tracking/<int:booking_id>')
def stream_tracking(booking_id):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("""
        SELECT b.current_worker_lat, b.current_worker_lon, w.latitude AS wrk_lat, w.longitude AS wrk_lon,
               u.latitude AS user_lat, u.longitude AS user_lon
        FROM bookings b
        JOIN workers w ON b.worker_id = w.id
        JOIN users u ON LOWER(b.customer_email) = LOWER(u.email)
        WHERE b.id = %s
    """, (booking_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    
    if row:
        active_lat = row['current_worker_lat'] if row['current_worker_lat'] else row['wrk_lat']
        active_lon = row['current_worker_lon'] if row['current_worker_lon'] else row['wrk_lon']
        
        dist_str, eta_str = calculate_distance_and_eta(float(active_lat), float(active_lon), float(row['user_lat']), float(row['user_lon']))
        return jsonify({
            "worker_lat": float(active_lat),
            "worker_lon": float(active_lon),
            "user_lat": float(row['user_lat']),
            "user_lon": float(row['user_lon']),
            "distance": dist_str,
            "eta": eta_str
        })
    return jsonify({"error": "Not Found"}), 404

@app.route('/worker-dashboard/<int:worker_id>')
def worker_dashboard(worker_id):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("""
        SELECT b.id, b.status, b.customer_phone, w.rating, w.review_count, u.name,
               u.latitude AS user_lat, u.longitude AS user_lon,
               COALESCE(b.current_worker_lat, w.latitude) AS wrk_lat,
               COALESCE(b.current_worker_lon, w.longitude) AS wrk_lon
        FROM bookings b 
        JOIN workers w ON b.worker_id = w.id 
        JOIN users u ON LOWER(b.customer_email) = LOWER(u.email)
        WHERE b.worker_id = %s ORDER BY b.id DESC
    """, (worker_id,))
    raw_jobs = cur.fetchall()
    
    jobs = []
    for r in raw_jobs:
        j_dict = dict(r)
        j_dict['user_lat'] = float(j_dict['user_lat'])
        j_dict['user_lon'] = float(j_dict['user_lon'])
        j_dict['wrk_lat'] = float(j_dict['wrk_lat'])
        j_dict['wrk_lon'] = float(j_dict['wrk_lon'])
        
        dist_str, _ = calculate_distance_and_eta(j_dict['wrk_lat'], j_dict['wrk_lon'], j_dict['user_lat'], j_dict['user_lon'])
        j_dict['distance_from_client'] = dist_str
        jobs.append(j_dict)
        
    trust = min(100, int((raw_jobs[0][3]*15)+(raw_jobs[0][4]*5))) if raw_jobs else 0
    cur.close(); conn.close()
    return render_template('worker_dashboard.html', jobs=jobs, worker_id=worker_id, trust=trust)

@app.route('/user-home')
def user_home():
    email = session.get('user_email')
    if not email: return redirect(url_for('login'))
    conn = get_db_connection(); cur = conn.cursor()
    
    cur.execute("""
        SELECT b.id, b.worker_id, w.name, b.status, w.daily_wage, w.job_expert, w.town_name,
               u.latitude AS user_lat, u.longitude AS user_lon,
               COALESCE(b.current_worker_lat, w.latitude) AS wrk_lat, 
               COALESCE(b.current_worker_lon, w.longitude) AS wrk_lon
        FROM bookings b 
        JOIN workers w ON b.worker_id = w.id 
        JOIN users u ON LOWER(b.customer_email) = LOWER(u.email)
        WHERE b.customer_email = %s ORDER BY b.id DESC
    """, (email,))
    raw_bookings = cur.fetchall()
    
    bookings = []
    for b in raw_bookings:
        b_dict = dict(b)
        b_dict['user_lat'] = float(b_dict['user_lat'])
        b_dict['user_lon'] = float(b_dict['user_lon'])
        b_dict['wrk_lat'] = float(b_dict['wrk_lat'])
        b_dict['wrk_lon'] = float(b_dict['wrk_lon'])
        
        if b_dict['status'] in ['ACCEPTED', 'PENDING']:
            dist_str, eta_str = calculate_distance_and_eta(b_dict['wrk_lat'], b_dict['wrk_lon'], b_dict['user_lat'], b_dict['user_lon'])
            b_dict['eta_display'] = f"{dist_str} away (Approx. {eta_str} to arrive)"
        bookings.append(b_dict)
        
    cur.close(); conn.close()
    return render_template('user_search.html', bookings=bookings, user_email=email)

@app.route('/search-jobs', methods=['POST'])
def search_jobs():
    query = request.form.get('job_type')
    user_id = session.get('user_id')
    
    conn = get_db_connection(); cur = conn.cursor()
    user_lat, user_lon = 12.9716, 77.5946
    if user_id:
        cur.execute("SELECT latitude, longitude FROM users WHERE id = %s", (user_id,))
        u_coord = cur.fetchone()
        if u_coord:
            user_lat = float(u_coord['latitude'])
            user_lon = float(u_coord['longitude'])
            
    cur.execute("SELECT id, name, job_expert, latitude, longitude, rating, daily_wage, review_count, town_name FROM workers WHERE job_expert ILIKE %s", (f'%{query}%',))
    workers = []
    for w in cur.fetchall():
        trust = min(100, int((w['rating']*15)+(w['review_count']*5)))
        worker_lat = float(w['latitude'])
        worker_lon = float(w['longitude'])
        
        dlat = math.radians(worker_lat - user_lat)
        dlon = math.radians(worker_lon - user_lon)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(user_lat)) * math.cos(math.radians(worker_lat)) * math.sin(dlon/2)**2
        dist = round(2 * 6371 * math.asin(math.sqrt(a)), 2)
        
        workers.append({
            'id': w['id'], 'name': w['name'], 'job': w['job_expert'], 
            'dist': dist, 'rating': w['rating'], 'wage': w['daily_wage'], 'trust': trust, 'town': w['town_name']
        })
    cur.close(); conn.close()
    return render_template('user_results.html', workers=sorted(workers, key=lambda x: x['dist']))

@app.route('/hire/<int:worker_id>')
def hire(worker_id):
    user_email = session.get('user_email')
    user_id = session.get('user_id')
    if not user_email: return redirect(url_for('login'))
    
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT phone FROM users WHERE id = %s", (user_id,))
    u_phone = cur.fetchone()
    phone_str = u_phone['phone'] if u_phone else '9845012345'
    
    cur.execute("INSERT INTO bookings (worker_id, customer_email, customer_phone, status, created_at) VALUES (%s, %s, %s, 'PENDING', CURRENT_TIMESTAMP)", (worker_id, user_email, phone_str))
    conn.commit(); cur.close(); conn.close()
    return redirect(url_for('user_home'))

@app.route('/job-action/<int:booking_id>/<string:action>')
def job_action(booking_id, action):
    if action == 'accept':
        status = 'ACCEPTED'
    elif action == 'reject':
        status = 'REJECTED'
    elif action == 'finish': 
        status = 'COMPLETED'
    else:
        status = 'PENDING'
        
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("UPDATE bookings SET status = %s WHERE id = %s", (status, booking_id))
    conn.commit(); cur.close(); conn.close()
    return redirect(request.referrer)

@app.route('/submit-rating/<int:booking_id>', methods=['POST'])
def submit_rating(booking_id):
    val = float(request.form.get('rating'))
    review_msg = request.form.get('review_text')
    
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT worker_id FROM bookings WHERE id = %s", (booking_id,))
    wid = cur.fetchone()[0]
    
    cur.execute("UPDATE workers SET rating=(rating*review_count+%s)/(review_count+1), review_count=review_count+1 WHERE id=%s", (val, wid))
    cur.execute("UPDATE bookings SET status='RATED', review_text=%s WHERE id=%s", (review_msg, booking_id))
    conn.commit(); cur.close(); conn.close()
    return redirect(url_for('user_home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)