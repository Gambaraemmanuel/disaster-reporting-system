from flask import Flask, render_template, request, redirect, session, flash, url_for
import sqlite3
import os
import uuid

app = Flask(__name__)
app.secret_key = "secretkey"

UPLOAD_FOLDER = "static/uploads"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------- Initialize Database ----------------
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT DEFAULT 'user'
    )''')

    # Reports table
    c.execute('''CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        disaster_type TEXT,
        description TEXT,
        location TEXT,
        image TEXT,
        status TEXT DEFAULT 'Pending'
    )''')

    # ---------------- Create Admin Account ----------------
    admin_email = "admin@example.com"
    admin_password = "1234"

    admin = c.execute(
        "SELECT id FROM users WHERE email=?",
        (admin_email,)
    ).fetchone()

    if admin:
        # Make sure the account is an admin
        c.execute(
            "UPDATE users SET password=?, role='admin' WHERE email=?",
            (admin_password, admin_email)
        )
    else:
        # Create the admin account
        c.execute(
            """INSERT INTO users (name, email, password, role)
               VALUES (?, ?, ?, ?)""",
            ("Administrator", admin_email, admin_password, "admin")
        )

    conn.commit()
    conn.close()
init_db()
# ---------------- Home ----------------
@app.route('/')
def index():
    return render_template('index.html')

# ---------------- Register ----------------
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (name,email,password) VALUES (?,?,?)",
                      (name,email,password))
            conn.commit()
        except sqlite3.IntegrityError:
            flash("Email already registered.")
            conn.close()
            return redirect('/register')
        conn.close()
        flash("Registration successful. Please login.")
        return redirect('/login')

    return render_template('register.html')

# ---------------- Login ----------------
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        user = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()

        if user:
            if user[3] == password:  # password check
                session['user_id'] = user[0]
                session['role'] = user[4]
                session['name'] = user[1]
                flash(f"Welcome {user[1]}!")
                return redirect('/admin') if user[4] == 'admin' else redirect('/dashboard')
            else:
                flash("Wrong password. Try again.")
                return redirect('/login')
        else:
            flash("Email not found. Please register first.")
            return redirect('/register')

    return render_template('login.html')

# ---------------- Dashboard ----------------
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    status_filter = request.args.get('status')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    if status_filter:
        reports = c.execute("""SELECT * FROM reports 
                               WHERE user_id=? AND status=?""",
                            (session['user_id'], status_filter)).fetchall()
    else:
        reports = c.execute("""SELECT * FROM reports 
                               WHERE user_id=?""",
                            (session['user_id'],)).fetchall()

    conn.close()
    return render_template('dashboard.html', reports=reports)

# ---------------- Report Disaster ----------------
@app.route('/report', methods=['GET','POST'])
def report():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        disaster_type = request.form['type']
        description = request.form['description']
        location = request.form['location']
        image = request.files.get('image')

        filename = None
        if image and image.filename != "":
            ext = os.path.splitext(image.filename)[1]  # preserve extension
            filename = str(uuid.uuid4()) + ext        # unique filename
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(path)

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("""INSERT INTO reports 
                     (user_id, disaster_type, description, location, image)
                     VALUES (?,?,?,?,?)""",
                  (session['user_id'], disaster_type, description, location, filename))
        conn.commit()
        conn.close()
        flash("Report submitted successfully.")
        return redirect('/dashboard')

    return render_template('report.html')

# ---------------- Admin Panel ----------------
@app.route('/admin')
def admin():
    if session.get('role') != 'admin':
        return "Access Denied"

    status_filter = request.args.get('status')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    if status_filter:
        reports = c.execute("SELECT * FROM reports WHERE status=?", 
                            (status_filter,)).fetchall()
    else:
        reports = c.execute("SELECT * FROM reports").fetchall()

    conn.close()
    return render_template('admin.html', reports=reports)

# ---------------- Update Status ----------------
@app.route('/update_status/<int:id>/<status>')
def update_status(id, status):
    if session.get('role') != 'admin':
        return "Unauthorized"

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE reports SET status=? WHERE id=?", (status, id))
    conn.commit()
    conn.close()
    flash("Status updated successfully.")
    return redirect('/admin')

# ---------------- Delete Report ----------------
@app.route('/delete_report/<int:id>')
def delete_report(id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    report = c.execute("SELECT user_id FROM reports WHERE id=?", (id,)).fetchone()
    if not report:
        conn.close()
        flash("Report not found.")
        return redirect('/dashboard')

    if session.get('role') == 'admin' or report[0] == session.get('user_id'):
        c.execute("DELETE FROM reports WHERE id=?", (id,))
        conn.commit()
        conn.close()
        flash("Report deleted successfully.")
        return redirect('/dashboard' if session.get('role') != 'admin' else '/admin')
    else:
        conn.close()
        flash("Unauthorized action.")
        return redirect('/dashboard')

# ---------------- Logout ----------------
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect('/')

# ---------------- Run App ----------------
if __name__ == '__main__':
    app.run(debug=True)
