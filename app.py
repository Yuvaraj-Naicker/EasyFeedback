from flask import Flask, render_template, request, redirect, send_file, session, url_for
import sqlite3
import pandas as pd
import os

from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "your_secret_key"  # change to a secure key

# ---------- DATABASE SETUP ----------
def init_db():
    conn = sqlite3.connect('feedback.db')
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS subjects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    subject_id INTEGER NOT NULL,
                    criteria TEXT NOT NULL,
                    rating INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    FOREIGN KEY (subject_id) REFERENCES subjects (id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )''')

    conn.commit()
    conn.close()

# ---------- USER AUTH ----------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        hashed_pw = generate_password_hash(password)

        conn = sqlite3.connect('feedback.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_pw))
            conn.commit()
            conn.close()
            return redirect('/login')
        except:
            conn.close()
            return "Username already exists!"

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('feedback.db')
        c = conn.cursor()
        c.execute("SELECT id, password FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            session['username'] = username
            return redirect('/admin')
        else:
            return "Invalid username or password!"

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ---------- ADMIN PANEL ----------
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    if request.method == 'POST':
        subject_name = request.form['subject']
        conn = sqlite3.connect('feedback.db')
        c = conn.cursor()
        c.execute("INSERT INTO subjects (name, user_id) VALUES (?, ?)", (subject_name, user_id))
        conn.commit()
        conn.close()

    conn = sqlite3.connect('feedback.db')
    c = conn.cursor()
    c.execute("SELECT * FROM subjects WHERE user_id = ?", (user_id,))
    subjects = c.fetchall()
    conn.close()

    return render_template('admin.html', subjects=subjects)


@app.route('/delete_subject/<int:subject_id>')
def delete_subject(subject_id):
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = sqlite3.connect('feedback.db')
    c = conn.cursor()
    c.execute("DELETE FROM feedback WHERE subject_id = ? AND user_id = ?", (subject_id, user_id))
    c.execute("DELETE FROM subjects WHERE id = ? AND user_id = ?", (subject_id, user_id))
    conn.commit()
    conn.close()
    return redirect('/admin')


@app.route('/new_feedback')
def new_feedback():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = sqlite3.connect('feedback.db')
    c = conn.cursor()
    c.execute("DELETE FROM feedback WHERE user_id = ?", (user_id,))
    c.execute("DELETE FROM subjects WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return redirect('/admin')


@app.route('/view_feedback')
def view_feedback():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = sqlite3.connect('feedback.db')
    df = pd.read_sql_query(
        '''SELECT feedback.student_id, subjects.name AS subject, 
                  feedback.criteria, feedback.rating
           FROM feedback
           JOIN subjects ON feedback.subject_id = subjects.id
           WHERE feedback.user_id = ?''', conn, params=(user_id,))
    conn.close()

    table_data = df.to_dict(orient='records')
    return render_template('view_feedback.html', feedbacks=table_data)


@app.route("/export_excel")
def export_excel():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("feedback.db")
    c = conn.cursor()
    c.execute("""
        SELECT s.name, f.student_id, f.criteria, f.rating
        FROM feedback f
        JOIN subjects s ON f.subject_id = s.id
        WHERE f.user_id = ?
    """, (session["user_id"],))
    rows = c.fetchall()
    conn.close()

    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["Subject", "Student ID", "Criteria", "Rating"])
    for row in rows:
        ws.append(row)

    file_path = "feedback_export.xlsx"
    wb.save(file_path)
    return send_file(file_path, as_attachment=True)

# ---------- FEEDBACK FORM ----------
@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    user_id = request.args.get('user_id')
    if not user_id:
        return "Invalid feedback link!"

    criteria_list = [
        "Aim/Objectives of the subject made clear",
        "Teaching is well planned and organized",
        "Teacher comes well prepared in the subject",
        "Teacher keeps himself/herself updated",
        "Subject matter organized in logical sequence",
        "Teacher speaks clearly and audibly",
        "Teacher explains concepts well with examples",
        "Pace and level suited to students",
        "Uses variety of teaching methods",
        "Comes to class on time regularly"
    ]

    conn = sqlite3.connect('feedback.db')
    c = conn.cursor()
    c.execute("SELECT * FROM subjects WHERE user_id = ?", (user_id,))
    subjects = c.fetchall()
    conn.close()

    if request.method == 'POST':
        student_id = request.form['student_id']
        for subj in subjects:
            subj_id = subj[0]
            for crit in criteria_list:
                rating = request.form.get(f"{subj_id}_{crit}")
                if rating:
                    conn = sqlite3.connect('feedback.db')
                    c = conn.cursor()
                    c.execute("INSERT INTO feedback (student_id, subject_id, criteria, rating, user_id) VALUES (?, ?, ?, ?, ?)",
                              (student_id, subj_id, crit, int(rating), user_id))
                    conn.commit()
                    conn.close()
        return redirect('/success')

    return render_template('feedback.html', subjects=subjects, criteria=criteria_list)


@app.route('/success')
def success():
    return render_template('success.html')


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
