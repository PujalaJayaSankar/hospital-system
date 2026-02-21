from flask import Flask, request, jsonify, send_from_directory, session, redirect, send_file,render_template_string
import sqlite3
from io import BytesIO

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

app = Flask(__name__)
app.secret_key = "hospital_secret_key_123"
@app.route("/test_session")
def test_session():
    return str(session)

@app.route('/analytics')
def analytics():

    # 🔐 Admin protection
    if not session.get("admin_logged_in"):
        return redirect('/login')

    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM appointments")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM appointments WHERE date=date('now')")
    today = cur.fetchone()[0]

    cur.execute("SELECT doctor, COUNT(*) FROM appointments GROUP BY doctor")
    doctor_data = cur.fetchall()

    doctors = [row[0] for row in doctor_data]
    counts = [row[1] for row in doctor_data]

    cur.execute("""
        SELECT strftime('%m', date), COUNT(*)
        FROM appointments
        GROUP BY strftime('%m', date)
    """)
    monthly_data = cur.fetchall()

    months = [row[0] for row in monthly_data]
    monthly_counts = [row[1] for row in monthly_data]

    cur.execute("""
        SELECT hospital, COUNT(*)
        FROM appointments
        GROUP BY hospital
    """)
    hospital_data = cur.fetchall()

    hospital_ids = [str(row[0]) for row in hospital_data]
    hospital_counts = [row[1] for row in hospital_data]

    conn.close()

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Analytics</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body { font-family: Arial; padding:30px; background:#f4f6f9; }
            .card {
                background:white;
                padding:20px;
                margin-bottom:20px;
                border-radius:10px;
                box-shadow:0 2px 5px rgba(0,0,0,0.1);
            }
        </style>
    </head>
    <body>

    <h2>Admin Analytics Dashboard</h2>

    <div class="card">
        <h3>Total Appointments: {{total}}</h3>
        <h3>Today's Appointments: {{today}}</h3>
    </div>

    <div class="card">
        <h3>Doctor Wise</h3>
        <canvas id="doctorChart"></canvas>
    </div>

    <div class="card">
        <h3>Monthly</h3>
        <canvas id="monthlyChart"></canvas>
    </div>

    <div class="card">
        <h3>Hospital Wise</h3>
        <canvas id="hospitalChart"></canvas>
    </div>

    <script>
    const doctors = {{doctors|tojson}};
    const counts = {{counts|tojson}};
    const months = {{months|tojson}};
    const monthlyCounts = {{monthly_counts|tojson}};
    const hospitals = {{hospital_ids|tojson}};
    const hospitalCounts = {{hospital_counts|tojson}};

    new Chart(document.getElementById('doctorChart'), {
        type: 'bar',
        data: {
            labels: doctors,
            datasets: [{
                label: 'Appointments',
                data: counts,
                backgroundColor: 'rgba(54,162,235,0.7)'
            }]
        }
    });

    new Chart(document.getElementById('monthlyChart'), {
        type: 'line',
        data: {
            labels: months,
            datasets: [{
                label: 'Monthly',
                data: monthlyCounts,
                borderColor: 'green',
                fill:false
            }]
        }
    });

    new Chart(document.getElementById('hospitalChart'), {
        type: 'pie',
        data: {
            labels: hospitals,
            datasets: [{
                data: hospitalCounts,
                backgroundColor: ['red','blue','green','orange','purple']
            }]
        }
    });
    </script>

    </body>
    </html>
    """, total=total,
         today=today,
         doctors=doctors,
         counts=counts,
         months=months,
         monthly_counts=monthly_counts,
         hospital_ids=hospital_ids,
         hospital_counts=hospital_counts)


# ------------------ DB INIT ------------------
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
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    cur.execute("SELECT * FROM admin WHERE username='admin'")
    if cur.fetchone() is None:
        cur.execute("INSERT INTO admin (username, password) VALUES (?, ?)", ("admin", "admin123"))

    conn.commit()
    conn.close()

init_db()


# ------------------ STATE/CITY (Major) ------------------
state_city = {
    "Andhra Pradesh": ["Visakhapatnam", "Vijayawada", "Guntur", "Tirupati"],
    "Karnataka": ["Bengaluru", "Mysuru", "Mangaluru"],
    "Kerala": ["Thiruvananthapuram", "Kochi", "Kozhikode"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai"],
    "Telangana": ["Hyderabad", "Warangal", "Karimnagar"],
    "Maharashtra": ["Mumbai", "Pune", "Nagpur"],
    "Delhi": ["New Delhi"],
    "West Bengal": ["Kolkata", "Siliguri"],
    "Uttar Pradesh": ["Lucknow", "Noida", "Kanpur"],
    "Gujarat": ["Ahmedabad", "Surat"],
    "Rajasthan": ["Jaipur", "Jodhpur"]
}


# ------------------ HOSPITALS (Realistic Names) ------------------
# Hospital list by State -> City -> Hospitals
hospitals = {
    "Telangana": {
        "Hyderabad": [
            "Apollo Hospitals, Jubilee Hills",
            "Yashoda Hospitals, Somajiguda",
            "KIMS Hospitals, Secunderabad",
            "Care Hospitals, Banjara Hills"
        ],
        "Warangal": [
            "MGM Hospital, Warangal",
            "Apex Hospital, Warangal"
        ],
        "Karimnagar": [
            "Sunrise Hospital, Karimnagar",
            "Medicover Hospitals, Karimnagar"
        ]
    },

    "Andhra Pradesh": {
        "Visakhapatnam": [
            "Apollo Hospitals, Visakhapatnam",
            "SevenHills Hospital, Vizag",
            "Care Hospitals, Vizag"
        ],
        "Vijayawada": [
            "Manipal Hospitals, Vijayawada",
            "Andhra Hospitals, Vijayawada",
            "Ramesh Hospitals, Vijayawada"
        ],
        "Guntur": [
            "NRI General Hospital, Guntur",
            "Amaravathi Hospitals, Guntur"
        ],
        "Tirupati": [
            "SVIMS, Tirupati",
            "Apollo Hospitals, Tirupati"
        ]
    },

    "Tamil Nadu": {
        "Chennai": [
            "Apollo Hospitals, Greams Road",
            "Fortis Malar Hospital",
            "MIOT International",
            "SRM Global Hospitals"
        ],
        "Coimbatore": [
            "Ganga Hospital, Coimbatore",
            "PSG Hospitals, Coimbatore"
        ],
        "Madurai": [
            "Apollo Speciality Hospital, Madurai",
            "Meenakshi Mission Hospital"
        ]
    },

    "Karnataka": {
        "Bengaluru": [
            "Manipal Hospital, Old Airport Road",
            "Fortis Hospital, Bannerghatta Road",
            "Narayana Health City",
            "Apollo Hospitals, Bannerghatta"
        ],
        "Mysuru": [
            "JSS Hospital, Mysuru",
            "Apollo BGS Hospitals, Mysuru"
        ],
        "Mangaluru": [
            "KMC Hospital, Mangaluru",
            "AJ Hospital, Mangaluru"
        ]
    },

    "Maharashtra": {
        "Mumbai": [
            "Lilavati Hospital, Bandra",
            "Kokilaben Hospital",
            "Hiranandani Hospital, Powai"
        ],
        "Pune": [
            "Ruby Hall Clinic",
            "Sahyadri Hospital, Pune",
            "Jehangir Hospital"
        ],
        "Nagpur": [
            "Wockhardt Hospitals, Nagpur",
            "Kingsway Hospitals, Nagpur"
        ]
    },

    "Delhi": {
        "New Delhi": [
            "AIIMS, New Delhi",
            "Fortis Escorts Heart Institute",
            "Max Super Speciality Hospital, Saket"
        ]
    },

    "West Bengal": {
        "Kolkata": [
            "AMRI Hospitals, Kolkata",
            "Apollo Gleneagles Hospitals",
            "Fortis Hospital, Anandapur"
        ],
        "Siliguri": [
            "Medica North Bengal Clinic",
            "Neotia Getwell Hospital"
        ]
    },

    "Uttar Pradesh": {
        "Lucknow": [
            "Medanta Hospital, Lucknow",
            "Apollo Medics Hospital, Lucknow"
        ],
        "Noida": [
            "Fortis Hospital, Noida",
            "Jaypee Hospital, Noida"
        ],
        "Kanpur": [
            "Regency Hospital, Kanpur",
            "Rama Hospital, Kanpur"
        ]
    },

    "Gujarat": {
        "Ahmedabad": [
            "Zydus Hospitals, Ahmedabad",
            "Apollo Hospitals, Ahmedabad"
        ],
        "Surat": [
            "Kiran Hospital, Surat",
            "New Civil Hospital, Surat"
        ]
    },

    "Rajasthan": {
        "Jaipur": [
            "Fortis Hospital, Jaipur",
            "SMS Hospital, Jaipur"
        ],
        "Jodhpur": [
            "AIIMS, Jodhpur",
            "Goyal Hospital, Jodhpur"
        ]
    }
}


# ------------------ DOCTORS (Hospital-wise) ------------------
# Doctors by Hospital -> Department
hospital_doctors = {
    # Default departments for all hospitals
    "ENT": [
        {"name": "Dr. Rajesh", "timing": "10:00 AM - 1:00 PM"},
        {"name": "Dr. Priya", "timing": "2:00 PM - 5:00 PM"}
    ],
    "Cardiology": [
        {"name": "Dr. Kumar", "timing": "11:00 AM - 2:00 PM"},
        {"name": "Dr. Anjali", "timing": "3:00 PM - 6:00 PM"}
    ],
    "Dental": [
        {"name": "Dr. Suresh", "timing": "9:00 AM - 12:00 PM"},
        {"name": "Dr. Meena", "timing": "1:00 PM - 4:00 PM"}
    ],
    "General": [
        {"name": "Dr. Ramesh", "timing": "10:00 AM - 6:00 PM"}
    ]
}


# ------------------ FIXED TIME SLOTS ------------------
ALL_SLOTS = [
    "10:00 AM", "10:15 AM", "10:30 AM", "10:45 AM",
    "11:00 AM", "11:15 AM", "11:30 AM", "11:45 AM",
    "12:00 PM", "12:15 PM", "12:30 PM", "12:45 PM",
    "01:00 PM"
]


# ------------------ PAGES ------------------
@app.route("/")
def home():
    return send_from_directory(".", "index.html")

@app.route("/login")
def login_page():
    return send_from_directory(".", "login.html")

@app.route("/admin")
def admin_page():
    if "admin_logged_in" not in session:
        return redirect("/login")
    return send_from_directory(".", "admin.html")


# ------------------ AUTH ------------------
@app.route("/admin_login", methods=["POST"])
def admin_login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM admin WHERE username=? AND password=?", (username, password))
    row = cur.fetchone()
    conn.close()

    if row:
        session["admin_logged_in"] = True
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "Invalid username or password"})

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ------------------ API: STATE/CITY/HOSPITAL ------------------
@app.route("/states", methods=["GET"])
def get_states():
    return jsonify(list(state_city.keys()))

@app.route("/cities/<state>", methods=["GET"])
def get_cities(state):
    return jsonify(state_city.get(state, []))

@app.route("/hospitals", methods=["POST"])
def get_hospitals():
    data = request.json
    state = data.get("state")
    city = data.get("city")

    state_data = hospitals.get(state, {})
    city_hospitals = state_data.get(city, [])
    return jsonify(city_hospitals)


# ------------------ API: DOCTORS ------------------
@app.route("/doctors/<department>", methods=["GET"])
def get_doctors(department):
    dept = department.strip()
    return jsonify(hospital_doctors.get(dept, []))


# ------------------ API: AVAILABLE SLOTS ------------------
@app.route("/available_slots", methods=["POST"])
def available_slots():
    data = request.json
    doctor = data.get("doctor")
    date = data.get("date")

    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT time FROM appointments
        WHERE doctor=? AND date=?
    """, (doctor, date))

    booked = [row[0] for row in cur.fetchall()]
    conn.close()

    free_slots = [s for s in ALL_SLOTS if s not in booked]
    return jsonify(free_slots)


# ------------------ BOOK APPOINTMENT ------------------
@app.route("/book", methods=["POST"])
def book():
    data = request.json

    name = data.get("name")
    phone = data.get("phone")
    state = data.get("state")
    city = data.get("city")
    hospital = data.get("hospital")
    department = data.get("department")
    doctor = data.get("doctor")
    date = data.get("date")
    time = data.get("time")

    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()

    # Slot check (Doctor + Date + Time)
    cur.execute("""
        SELECT * FROM appointments
        WHERE doctor=? AND date=? AND time=?
    """, (doctor, date, time))

    if cur.fetchone():
        conn.close()
        return jsonify({"success": False, "message": "❌ Slot already booked! Choose another time."})

    cur.execute("""
        INSERT INTO appointments (name, phone, state, city, hospital, department, doctor, date, time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, phone, state, city, hospital, department, doctor, date, time))

    appointment_id = cur.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "✅ Appointment booked successfully!",
        "appointment_id": appointment_id
    })


# ------------------ ADMIN: VIEW ALL ------------------
@app.route("/appointments", methods=["GET"])
def appointments():
    if "admin_logged_in" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM appointments ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "id": r[0],
            "name": r[1],
            "phone": r[2],
            "state": r[3],
            "city": r[4],
            "hospital": r[5],
            "department": r[6],
            "doctor": r[7],
            "date": r[8],
            "time": r[9]
        })

    return jsonify(result)


# ------------------ ADMIN: REPORT ------------------
@app.route("/report", methods=["POST"])
def report():
    if "admin_logged_in" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    doctor = data.get("doctor")
    date = data.get("date")

    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, phone, state, city, hospital, department, doctor, date, time
        FROM appointments
        WHERE doctor=? AND date=?
        ORDER BY time ASC
    """, (doctor, date))

    rows = cur.fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "id": r[0],
            "name": r[1],
            "phone": r[2],
            "state": r[3],
            "city": r[4],
            "hospital": r[5],
            "department": r[6],
            "doctor": r[7],
            "date": r[8],
            "time": r[9]
        })

    return jsonify(result)


# ------------------ ADMIN: DELETE ------------------
@app.route("/delete/<int:appointment_id>", methods=["DELETE"])
def delete_appointment(appointment_id):
    if "admin_logged_in" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": "Appointment deleted successfully!"})


# ------------------ PDF GENERATION ------------------
@app.route("/pdf/<int:appointment_id>", methods=["GET"])
def generate_pdf(appointment_id):
    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, phone, state, city, hospital, department, doctor, date, time
        FROM appointments
        WHERE id=?
    """, (appointment_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return "Appointment not found", 404

    appt = {
        "id": row[0],
        "name": row[1],
        "phone": row[2],
        "state": row[3],
        "city": row[4],
        "hospital": row[5],
        "department": row[6],
        "doctor": row[7],
        "date": row[8],
        "time": row[9]
    }

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()

    elements = []
    elements.append(Paragraph("Hospital Appointment Slip", styles["Title"]))
    elements.append(Spacer(1, 15))

    table_data = [
        ["Appointment ID", str(appt["id"])],
        ["Patient Name", appt["name"]],
        ["Phone Number", appt["phone"]],
        ["State", appt["state"]],
        ["City", appt["city"]],
        ["Hospital", appt["hospital"]],
        ["Department", appt["department"]],
        ["Doctor", appt["doctor"]],
        ["Date", appt["date"]],
        ["Time", appt["time"]],
    ]

    table = Table(table_data, colWidths=[160, 320])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.7, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("PADDING", (0, 0), (-1, -1), 10),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Please arrive 10 minutes early. Thank you!", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"appointment_{appointment_id}.pdf",
        mimetype="application/pdf"
    )


if __name__ == "__main__":
    app.run()