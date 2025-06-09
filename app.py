from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor


app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to something secure

# --- Neon PostgreSQL config ---
DB_HOST = "ep-black-hill-a90huo8r-pooler.gwc.azure.neon.tech"
DB_NAME = "neodbtracker"
DB_USER = "neodbtracker_owner"
DB_PASS = "npg_4H1GzoMVLnCO"
DB_SSLMODE = "require"

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        sslmode=DB_SSLMODE
    )
@app.template_filter('strftime')
def _jinja2_filter_datetime(date, fmt='%Y-%m-%d'):
    return date.strftime(fmt)


# --- Register Route ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['reg_username']
        password = request.form['reg_password']

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        existing_user = cur.fetchone()

        if existing_user:
            flash('Username already exists.', 'danger')
        else:
            hashed_password = generate_password_hash(password)
            cur.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, hashed_password))
            conn.commit()
            flash('Registration successful. Please log in.', 'success')

        cur.close()
        conn.close()
        return redirect(url_for('login'))

    return render_template('login.html')

# --- Login Route ---
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, password_hash FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            session['username'] = username
            return redirect(url_for('homepage'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('login.html')

# --- Dashboard Route ---
@app.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM trucks")
    total_trucks = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM trucks WHERE status = 'In Transit'")
    in_transit = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM trucks WHERE status = 'Available'")
    available = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM trucks WHERE status = 'Under Service'")
    under_service = cur.fetchone()[0]

    cur.close()
    conn.close()

    return render_template(
        'dashboard.html',
        total_trucks=total_trucks,
        in_transit=in_transit,
        available=available,
        under_service=under_service
    )


# --- Add Truck ---
@app.route('/add_truck', methods=['GET', 'POST'])
def add_truck():
    if request.method == 'POST':
        truck_id = request.form['truck_id']
        model = request.form['model']
        year_made = request.form['year_made']
        capacity = request.form['capacity']
        registration_number = request.form['registration_number']
        status = request.form['status']

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO trucks (truck_id, model, year_made, capacity, registration_number, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (truck_id, model, year_made, capacity, registration_number, status))
        conn.commit()
        cur.close()
        conn.close()

        flash('Truck added successfully!', 'success')
        return redirect(url_for('manage_trucks'))

    return render_template('add_truck.html')

# --- Edit Truck ---
@app.route('/edit_truck/<truck_id>', methods=['GET', 'POST'])
def edit_truck(truck_id):
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        model = request.form['model']
        year_made = request.form['year_made']
        capacity = request.form['capacity']
        registration_number = request.form['registration_number']
        status = request.form['status']

        cur.execute("""
            UPDATE trucks
            SET model = %s, year_made = %s, capacity = %s, registration_number = %s, status = %s
            WHERE truck_id = %s
        """, (model, year_made, capacity, registration_number, status, truck_id))
        conn.commit()
        cur.close()
        conn.close()
        flash("Truck updated successfully.", "success")
        return redirect(url_for('manage_trucks'))

    # GET request
    cur.execute("SELECT * FROM trucks WHERE truck_id = %s", (truck_id,))
    truck = cur.fetchone()
    cur.close()
    conn.close()

    if truck is None:
        return "Truck not found", 404

    return render_template("edit_truck.html", truck=truck)

# --- Delete Truck ---
@app.route('/delete_truck/<truck_id>', methods=['GET'])
def delete_truck(truck_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM trucks WHERE truck_id = %s", (truck_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("Truck deleted successfully.", "info")
    return redirect(url_for('manage_trucks'))

# --- Manage Trucks ---
@app.route('/manage_trucks')
def manage_trucks():
    conn = get_db_connection()
    cur = conn.cursor()

    truck_id = request.args.get('truck_id')
    status = request.args.get('status')
    model = request.args.get('model')

    query = "SELECT * FROM trucks  WHERE TRUE"
    params = []

    if truck_id:
        query += " AND truck_id ILIKE %s"
        params.append(f"%{truck_id}%")
    if status:
        query += " AND status = %s"
        params.append(status)
    if model:
        query += " AND model ILIKE %s"
        params.append(f"%{model}%")

    cur.execute(query, params)
    trucks = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("manage_trucks.html", trucks=trucks)

@app.route('/booking-trucks', methods=['GET', 'POST'])
def booking_trucks():
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        client = request.form['client_name']
        desc = request.form['job_description']
        date = request.form['booking_date']
        truck_id = request.form['truck_id']

        # Insert booking
        cur.execute("""
            INSERT INTO bookings (truck_id, client_name, job_description, booking_date)
            VALUES (%s, %s, %s, %s)
        """, (truck_id, client, desc, date))

        # Update truck status to "In Transit"
        cur.execute("""
            UPDATE trucks SET status = 'In Transit' WHERE truck_id = %s
        """, (truck_id,))

        conn.commit()
        flash("Truck booked successfully!", "success")
        return redirect(url_for('booking_trucks'))

    # Get only trucks with status 'Available'
    cur.execute("SELECT * FROM trucks WHERE status = 'Available'")
    available_trucks = cur.fetchall()

    # Get all bookings
    cur.execute("SELECT * FROM bookings ORDER BY booking_date DESC")
    bookings = cur.fetchall()

    cur.close()
    conn.close()
    return render_template("booking_trucks.html", available_trucks=available_trucks, bookings=bookings)

@app.route('/edit-booking/<int:booking_id>', methods=['GET', 'POST'])
def edit_booking(booking_id):
    conn = get_db_connection()
    # Use RealDictCursor so we can access columns by name (not by index!)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if request.method == 'POST':
        client_name = request.form['client_name']
        job_description = request.form['job_description']
        booking_date = request.form['booking_date']
        truck_id = request.form['truck_id']

        print("🔧 Debug: truck_id from form =", truck_id)

        try:
            cur.execute("""
                UPDATE bookings
                SET client_name = %s,
                    job_description = %s,
                    booking_date = %s,
                    truck_id = %s
                WHERE booking_id = %s
            """, (client_name, job_description, booking_date, truck_id, booking_id))
            conn.commit()
            flash("Booking updated successfully!", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Error updating booking: {str(e)}", "danger")
        finally:
            cur.close()
            conn.close()

        return redirect(url_for('booking_trucks'))

    # GET request — fetch booking to edit
    cur.execute("SELECT * FROM bookings WHERE booking_id = %s", (booking_id,))
    booking = cur.fetchone()

    if not booking:
        flash("Booking not found!", "danger")
        cur.close()
        conn.close()
        return redirect(url_for('booking_trucks'))

    # Get all trucks that are available OR the one currently assigned to this booking
    cur.execute("""
        SELECT * FROM trucks 
        WHERE status = 'Available' OR truck_id = %s
    """, (booking['truck_id'],))
    available_trucks = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("edit_booking.html", booking=booking, available_trucks=available_trucks)

@app.route('/delete-booking/<booking_id>', methods=['POST'])
def delete_booking(booking_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Optional: Get truck_id for status update (if needed)
    cur.execute("SELECT truck_id FROM bookings WHERE booking_id = %s", (booking_id,))
    truck = cur.fetchone()

    # Delete the booking
    cur.execute("DELETE FROM bookings WHERE booking_id = %s", (booking_id,))

    # If truck was found, mark it as "Available"
    if truck:
        cur.execute("UPDATE trucks SET status = 'Available' WHERE truck_id = %s", (truck[0],))

    conn.commit()
    cur.close()
    conn.close()

    flash("Booking deleted successfully.", "success")
    return redirect(url_for('booking_trucks'))

@app.route('/truck/<truck_id>')
def truck_details(truck_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Get truck info from trucks table
    cur.execute("SELECT * FROM trucks WHERE truck_id = %s", (truck_id,))
    truck = cur.fetchone()

    if not truck:
        return "Truck not found", 404

    # Get maintenance history from maintenance_history table
    cur.execute("""
        SELECT maintenance_date, description, resolved_by, cost, next_service_date 
        FROM maintenance_history 
        WHERE truck_id = %s 
        ORDER BY maintenance_date DESC
    """, (truck_id,))
    maintenance_records = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('truck_details.html', truck=truck, maintenance_records=maintenance_records)



# --- Homepage ---
@app.route('/homepage')
def homepage():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT truck_id, model FROM trucks")
    trucks = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('homepage.html', username=session['username'], trucks=trucks)

@app.route('/list_trucks')
def list_trucks():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT truck_id, model FROM trucks")
    trucks = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('list_trucks.html', trucks=trucks)


# --- Logout ---
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)

