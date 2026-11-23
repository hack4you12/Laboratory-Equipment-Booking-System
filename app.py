import os
import sqlite3
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
DB_PATH = os.path.join(os.path.dirname(__file__), "lab_booking.db")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('student','faculty','assistant','admin'))
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS equipment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                condition TEXT NOT NULL DEFAULT 'Good',
                status TEXT NOT NULL DEFAULT 'Available'
            )
        """)
        con.execute("""CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER NOT NULL REFERENCES equipment(id),
            student_id INTEGER NOT NULL REFERENCES users(id),
            start_at TEXT NOT NULL,
            end_at TEXT NOT NULL,
            purpose TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending','Approved','Rejected','Cancelled')),
            faculty_id INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        count = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            demo_users = [
                ("Aarav Student", "student@lab.com", "Student@123", "student"),
                ("Dr. Faculty", "faculty@lab.com", "Faculty@123", "faculty"),
                ("Lab Assistant", "assistant@lab.com", "Assistant@123", "assistant"),
                ("System Admin", "admin@lab.com", "Admin@123", "admin"),
            ]
            for name, email, password, role in demo_users:
                con.execute(
                    "INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
                    (name, email, generate_password_hash(password), role)
                )
        count = con.execute("SELECT COUNT(*) FROM equipment").fetchone()[0]
        if count == 0:
            con.executemany(
                "INSERT INTO equipment(name,category,condition,status) VALUES(?,?,?,?)",
                [
                    ("Digital Microscope", "Microscopy", "Good", "Available"),
                    ("Oscilloscope", "Electronics", "Good", "Available"),
                    ("3D Printer", "Prototyping", "Needs inspection", "Under Maintenance"),
                    ("Centrifuge", "Biology", "Good", "Available"),
                ]
            )

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if session.get("role") not in roles:
                flash("You do not have permission to access that page.", "error")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator

@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with db() as con:
            user = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    with db() as con:
        equipment = con.execute("SELECT * FROM equipment ORDER BY name").fetchall()
    return render_template("dashboard.html", equipment=equipment)

@app.route("/equipment/add", methods=["POST"])
@role_required("admin", "assistant")
def add_equipment():
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    if name and category:
        with db() as con:
            con.execute("INSERT INTO equipment(name,category) VALUES(?,?)", (name, category))
        flash("Equipment added successfully.", "success")
    else:
        flash("Enter both equipment name and category.", "error")
    return redirect(url_for("dashboard"))

@app.route("/equipment/<int:equipment_id>/status", methods=["POST"])
@role_required("assistant", "admin")
def update_equipment_status(equipment_id):
    status = request.form.get("status")
    condition = request.form.get("condition")
    allowed_status = {"Available", "Under Maintenance", "Out of Service"}
    allowed_condition = {"Good", "Needs inspection", "Damaged"}
    if status not in allowed_status or condition not in allowed_condition:
        flash("Invalid equipment status or condition.", "error")
        return redirect(url_for("dashboard"))
    with db() as con:
        con.execute(
            "UPDATE equipment SET status=?, condition=? WHERE id=?",
            (status, condition, equipment_id)
        )
    flash("Equipment status updated.", "success")
    return redirect(url_for("dashboard"))


@app.route("/bookings", methods=["GET", "POST"])
@role_required("student")
def bookings():
    with db() as con:
        if request.method == "POST":
            try:
                equipment_id = int(request.form.get("equipment_id", ""))
                start_at = datetime.fromisoformat(request.form.get("start_at", ""))
                end_at = datetime.fromisoformat(request.form.get("end_at", ""))
                purpose = request.form.get("purpose", "").strip()
                if not purpose or start_at >= end_at or start_at <= datetime.now():
                    raise ValueError("Enter a purpose and a valid future time range.")
                if (end_at-start_at).total_seconds() > 4*3600:
                    raise ValueError("Maximum booking duration is four hours.")
                item = con.execute("SELECT * FROM equipment WHERE id=?", (equipment_id,)).fetchone()
                if not item or item["status"] != "Available":
                    raise ValueError("Equipment is unavailable.")
                start, end = start_at.isoformat(timespec="minutes"), end_at.isoformat(timespec="minutes")
                conflict = con.execute("""SELECT 1 FROM bookings WHERE equipment_id=?
                    AND status IN ('Pending','Approved') AND start_at < ? AND end_at > ?""",
                    (equipment_id, end, start)).fetchone()
                if conflict:
                    raise ValueError("This time overlaps with another pending or approved booking.")
                con.execute("""INSERT INTO bookings(equipment_id,student_id,start_at,end_at,purpose)
                    VALUES(?,?,?,?,?)""", (equipment_id, session["user_id"], start, end, purpose))
                flash("Booking request submitted for faculty review.", "success")
                return redirect(url_for("bookings"))
            except (ValueError, TypeError) as exc:
                flash(str(exc) if str(exc) else "Invalid booking details.", "error")
        equipment = con.execute("SELECT * FROM equipment ORDER BY name").fetchall()
        mine = con.execute("""SELECT b.*,e.name AS equipment_name FROM bookings b
            JOIN equipment e ON e.id=b.equipment_id WHERE b.student_id=? ORDER BY b.id DESC""",
            (session["user_id"],)).fetchall()
    return render_template("bookings.html", equipment=equipment, mine=mine)

@app.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@role_required("student")
def cancel_booking(booking_id):
    with db() as con:
        result = con.execute("""UPDATE bookings SET status='Cancelled' WHERE id=?
            AND student_id=? AND status IN ('Pending','Approved')""", (booking_id, session["user_id"]))
    flash("Booking cancelled." if result.rowcount else "Booking cannot be cancelled.",
          "success" if result.rowcount else "error")
    return redirect(url_for("bookings"))

@app.route("/approvals")
@role_required("faculty")
def approvals():
    with db() as con:
        requests = con.execute("""SELECT b.*,e.name AS equipment_name,u.name AS student_name
            FROM bookings b JOIN equipment e ON e.id=b.equipment_id
            JOIN users u ON u.id=b.student_id ORDER BY b.id DESC""").fetchall()
    return render_template("approvals.html", requests=requests)

@app.route("/approvals/<int:booking_id>/<decision>", methods=["POST"])
@role_required("faculty")
def decide_booking(booking_id, decision):
    if decision not in ("Approved", "Rejected"):
        flash("Invalid decision.", "error")
        return redirect(url_for("approvals"))
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        booking = con.execute("""SELECT b.*,e.status AS equipment_status FROM bookings b
            JOIN equipment e ON e.id=b.equipment_id WHERE b.id=?""", (booking_id,)).fetchone()
        if not booking or booking["status"] != "Pending":
            flash("Request is no longer pending.", "error")
        elif decision == "Approved" and booking["equipment_status"] != "Available":
            flash("Equipment is unavailable.", "error")
        else:
            conflict = None
            if decision == "Approved":
                conflict = con.execute("""SELECT 1 FROM bookings WHERE id<>? AND equipment_id=?
                    AND status='Approved' AND start_at < ? AND end_at > ?""",
                    (booking_id, booking["equipment_id"], booking["end_at"], booking["start_at"])).fetchone()
            if conflict:
                flash("Overlapping approved booking exists.", "error")
            else:
                con.execute("UPDATE bookings SET status=?,faculty_id=? WHERE id=?",
                            (decision, session["user_id"], booking_id))
                flash("Request " + decision.lower() + ".", "success")
    return redirect(url_for("approvals"))

@app.route("/utilization")
@role_required("admin")
def utilization():
    with db() as con:
        rows = con.execute("""SELECT e.name,
            COUNT(b.id) AS total_requests,
            COALESCE(SUM(CASE WHEN b.status='Approved' THEN 1 ELSE 0 END),0) AS approved_count,
            COALESCE(SUM(CASE WHEN b.status='Approved' THEN
                (julianday(b.end_at)-julianday(b.start_at))*24 ELSE 0 END),0) AS approved_hours
            FROM equipment e LEFT JOIN bookings b ON b.equipment_id=e.id
            GROUP BY e.id ORDER BY e.name""").fetchall()
    return render_template("utilization.html", rows=rows)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
