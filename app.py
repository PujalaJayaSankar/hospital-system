from flask import Flask, request, jsonify, send_from_directory, session, redirect, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

app = Flask(__name__)
app.secret_key = "hospital_secret_key_123"

# ---------------- STATE / CITY ----------------

state_city = {
    "Andhra Pradesh": ["Visakhapatnam", "Vijayawada"],
    "Telangana": ["Hyderabad", "Warangal"],
    "Karnataka": ["Bengaluru"],
    "Tamil Nadu": ["Chennai"]
}

hospitals_data = {
    "Andhra Pradesh": {
        "Visakhapatnam": ["Apollo Vizag"],
        "Vijayawada": ["Ramesh Hospital"]
    },
    "Telangana": {
        "Hyderabad": ["Apollo Hyderabad"],
        "Warangal": ["MGM Hospital"]
    },
    "Karnataka": {
        "Bengaluru": ["Manipal Hospital"]
    },
    "Tamil Nadu": {
        "Chennai": ["Apollo Chennai"]
    }
}

doctor_data = {
    "ENT": [{"name": "Dr. Rajesh", "timing": "10:00 AM - 1:00 PM"}],
    "Dental": [{"name": "Dr. Meena", "timing": "9:00 AM - 12:00 PM"}],
    "Cardiology": [{"name": "Dr. Kumar", "timing": "11:00 AM - 2:00 PM"}],
    "General": [{"name": "Dr. Ramesh", "timing": "10:00 AM - 6:00 PM"}]
}

ALL_SLOTS = [
    "10:00 AM","10:15 AM","10:30 AM","10:45 AM",
    "11:00 AM","11:15 AM","11:30 AM"
]

# ---------------- DATABASE ----------------

def init_db():
    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            state TEXT,
            city TEXT,
            hospital TEXT,
            department TEXT,
            doctor TEXT,
            date TEXT,
            time TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    """)

    # Admin
    cur.execute("SELECT * FROM users WHERE username='admin'")
    if not cur.fetchone():
        cur.execute("INSERT INTO users VALUES (NULL,?,?,?)",
                    ("admin", generate_password_hash("admin123"), "admin"))

    # ----------- ADD ALL DOCTORS AS USERS -----------
    all_doctors = ["Dr. Rajesh", "Dr. Meena", "Dr. Kumar", "Dr. Ramesh"]

    for doctor in all_doctors:
        cur.execute("SELECT * FROM users WHERE username=?", (doctor,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO users (username,password,role) VALUES (?,?,?)",
                (doctor, generate_password_hash("doctor123"), "doctor")
            )

    conn.commit()
    conn.close()

init_db()

# ---------------- STATIC PAGES ----------------

@app.route("/")
def home():
    return send_from_directory(".", "index.html")

@app.route("/login")
def login_page():
    return send_from_directory(".", "login.html")

@app.route("/admin")
def admin_page():
    if session.get("role") != "admin":
        return redirect("/login")
    return send_from_directory(".", "admin.html")

@app.route("/analytics")
def analytics_page():
    if session.get("role") != "admin":
        return redirect("/login")
    return send_from_directory(".", "analytics.html")

# ----------- NEW DOCTOR PAGE ROUTE -----------

@app.route("/doctor")
def doctor_page():
    if session.get("role") != "doctor":
        return redirect("/login")
    return send_from_directory(".", "doctor.html")

# ---------------- AUTH ----------------

@app.route("/login_user", methods=["POST"])
def login_user():

    data = request.json
    username = data["username"]
    password = data["password"]

    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()
    cur.execute("SELECT password, role FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()

    if row and check_password_hash(row[0], password):

        session["username"] = username
        session["role"] = row[1]

        return jsonify({
            "success": True,
            "role": row[1]
        })

    return jsonify({
        "success": False,
        "message": "Invalid username or password"
    })
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------------- CHATBOT APIs ----------------

@app.route("/states")
def get_states():
    return jsonify(list(state_city.keys()))

@app.route("/cities/<state>")
def get_cities(state):
    return jsonify(state_city.get(state, []))

@app.route("/hospitals", methods=["POST"])
def get_hospitals():
    data = request.json
    return jsonify(hospitals_data.get(data["state"], {}).get(data["city"], []))

@app.route("/doctors/<department>")
def get_doctors(department):
    return jsonify(doctor_data.get(department, []))

@app.route("/available_slots", methods=["POST"])
def available_slots():
    data = request.json
    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()
    cur.execute("SELECT time FROM appointments WHERE doctor=? AND date=?",
                (data["doctor"], data["date"]))
    booked = [r[0] for r in cur.fetchall()]
    conn.close()
    return jsonify([s for s in ALL_SLOTS if s not in booked])

@app.route("/book", methods=["POST"])
def book():
    data = request.json
    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()

    cur.execute("SELECT * FROM appointments WHERE doctor=? AND date=? AND time=?",
                (data["doctor"], data["date"], data["time"]))

    if cur.fetchone():
        conn.close()
        return jsonify({"success": False, "message": "Slot already booked"})

    cur.execute("""
        INSERT INTO appointments
        (name, phone, state, city, hospital, department, doctor, date, time)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (
        data["name"], data["phone"], data["state"], data["city"],
        data["hospital"], data["department"], data["doctor"],
        data["date"], data["time"]
    ))

    appointment_id = cur.lastrowid
    conn.commit()
    conn.close()

    return jsonify({"success": True, "appointment_id": appointment_id})

# ---------------- ANALYTICS API ----------------

@app.route("/analytics_data")
def analytics_data():

    if session.get("role") != "admin":
        return jsonify({"error": "Unauthorized"}), 401

    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()

    # Total appointments
    cur.execute("SELECT COUNT(*) FROM appointments")
    total = cur.fetchone()[0]

    # Today's appointments
    from datetime import datetime
    today = datetime.now().strftime("%d-%m-%Y")
    cur.execute("SELECT COUNT(*) FROM appointments WHERE date=?", (today,))
    today_count = cur.fetchone()[0]

    # Doctor wise
    cur.execute("""
        SELECT doctor, COUNT(*)
        FROM appointments
        GROUP BY doctor
    """)
    doctor_data = cur.fetchall()

    # Monthly (based on MM-YYYY from DD-MM-YYYY)
    cur.execute("""
        SELECT SUBSTR(date,4,7) as month, COUNT(*)
        FROM appointments
        GROUP BY month
    """)
    monthly_data = cur.fetchall()

    # Hospital wise
    cur.execute("""
        SELECT hospital, COUNT(*)
        FROM appointments
        GROUP BY hospital
    """)
    hospital_data = cur.fetchall()

    conn.close()

    return jsonify({
        "total": total,
        "today": today_count,
        "doctor_data": doctor_data,
        "monthly_data": monthly_data,
        "hospital_data": hospital_data
    })
# ---------------- DOCTOR DASHBOARD ----------------

@app.route("/doctor_dashboard")
def doctor_dashboard():
    if session.get("role") != "doctor":
        return jsonify({"error": "Unauthorized"}), 401

    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()

    cur.execute("""
        SELECT name, hospital, date, time
        FROM appointments
        WHERE doctor=?
        ORDER BY date
    """, (session["username"],))

    rows = cur.fetchall()
    conn.close()

    return jsonify(rows)
# ---------------- ADMIN APPOINTMENTS LIST ----------------

@app.route("/appointments")
def get_appointments():

    if session.get("role") != "admin":
        return jsonify([]), 401

    conn = sqlite3.connect("appointments.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM appointments ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])


# ---------------- DELETE APPOINTMENT ----------------

@app.route("/delete/<int:appointment_id>", methods=["DELETE"])
def delete_appointment(appointment_id):

    if session.get("role") != "admin":
        return jsonify({"error": "Unauthorized"}), 401

    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()

    cur.execute("DELETE FROM appointments WHERE id=?", (appointment_id,))
    conn.commit()
    conn.close()

    return jsonify({"success": True})


# ---------------- DOCTOR DAILY REPORT ----------------

@app.route("/report", methods=["POST"])
def report():

    if session.get("role") != "admin":
        return jsonify([]), 401

    data = request.json
    doctor = data["doctor"]
    date = data["date"]

    conn = sqlite3.connect("appointments.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM appointments
        WHERE doctor=? AND date=?
        ORDER BY time
    """, (doctor, date))

    rows = cur.fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])

# ---------------- PDF ----------------

@app.route("/pdf/<int:appointment_id>")
def generate_pdf(appointment_id):
    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM appointments WHERE id=?", (appointment_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return "Not found", 404

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()

    elements = []
    elements.append(Paragraph("Hospital Appointment Slip", styles["Title"]))
    elements.append(Spacer(1, 15))

    table_data = [
        ["Patient", row[1]],
        ["Doctor", row[7]],
        ["Date", row[8]],
        ["Time", row[9]],
    ]

    table = Table(table_data)
    table.setStyle(TableStyle([("GRID",(0,0),(-1,-1),1,colors.black)]))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)

    return send_file(buffer,
                     as_attachment=True,
                     download_name=f"appointment_{appointment_id}.pdf",
                     mimetype="application/pdf")

if __name__ == "__main__":
    app.run()