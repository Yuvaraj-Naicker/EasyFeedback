from flask import Flask, render_template, request, redirect, send_file, session, url_for
import sqlite3
import pandas as pd
import os
from werkzeug.security import generate_password_hash, check_password_hash
import io
import xlsxwriter
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
@app.route('/', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pw = generate_password_hash(password)
        conn = sqlite3.connect('feedback.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                      (username, hashed_pw))
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
        c.execute("SELECT id, password FROM users WHERE username = ?",
                  (username, ))
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
        c.execute("INSERT INTO subjects (name, user_id) VALUES (?, ?)",
                  (subject_name, user_id))
        conn.commit()
        conn.close()
    conn = sqlite3.connect('feedback.db')
    c = conn.cursor()
    c.execute("SELECT * FROM subjects WHERE user_id = ?", (user_id, ))
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
    c.execute("DELETE FROM feedback WHERE subject_id = ? AND user_id = ?",
              (subject_id, user_id))
    c.execute("DELETE FROM subjects WHERE id = ? AND user_id = ?",
              (subject_id, user_id))
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
    c.execute("DELETE FROM feedback WHERE user_id = ?", (user_id, ))
    c.execute("DELETE FROM subjects WHERE user_id = ?", (user_id, ))
    conn.commit()
    conn.close()
    return redirect('/admin')


# ---------- MODIFIED VIEW_FEEDBACK ----------
@app.route('/view_feedback')
def view_feedback():
    if 'user_id' not in session:
        return redirect('/login')
    user_id = session['user_id']
    conn = sqlite3.connect('feedback.db')

    df = pd.read_sql_query('''SELECT 
                subjects.name AS subject,
                feedback.criteria,
                AVG(feedback.rating) as avg_rating
           FROM feedback
           JOIN subjects ON feedback.subject_id = subjects.id
           WHERE feedback.user_id = ?
           GROUP BY subjects.name, feedback.criteria
           ORDER BY subjects.name, feedback.criteria
        ''',
                           conn,
                           params=(user_id, ))
    conn.close()
    table_data = df.to_dict(orient='records')
    return render_template('view_feedback.html', feedbacks=table_data)


# ---------- EXPORT EXCEL (MODIFIED for averages) -----------
@app.route('/export_excel')
def export_excel():
    if 'user_id' not in session:
        return redirect('/login')
    user_id = session['user_id']
    conn = sqlite3.connect('feedback.db')
    df = pd.read_sql_query('''SELECT 
                subjects.name AS subject,
                feedback.criteria,
                AVG(feedback.rating) as avg_rating
           FROM feedback
           JOIN subjects ON feedback.subject_id = subjects.id
           WHERE feedback.user_id = ?
           GROUP BY subjects.name, feedback.criteria
           ORDER BY subjects.name, feedback.criteria
        ''',
                           conn,
                           params=(user_id, ))
    conn.close()
    file_path = f"feedback_report_{session['username']}.xlsx"
    df.to_excel(file_path, index=False)
    return send_file(file_path, as_attachment=True)


# ---------- FEEDBACK FORM ----------
@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    user_id = request.args.get('user_id')
    if not user_id:
        return "Invalid feedback link!"
    criteria_list = [
        "1.0 PLANNING AND ORGANISATION",
        "1.1 Teaching is well planned. Subject coverage schedule announced at the beginning of the semester",
        "1.2 Aim / Objectives of the subject made clear",
        "1.3 Teacher comes well prepared in the subject",
        "1.4 Teacher keeps himself / herself updated",
        "1.5 Subject matter organized in logical sequence",
        "2.0 PRESENTATION / COMMUNICATION",
        "2.1 Teacher speaks clearly and audibly",
        "2.2 Teacher writes and draws legibly",
        "2.3 Teacher explains concepts well, provides adequate examples.",
        "2.4 Teacher’s pace and level of instruction are suited to the attainment of students",
        "2.5 Teacher uses variety of methods and materials (OHP, Power Points, models etc.)",
        "3.0 CLASS MANAGEMENT AND STUDENT’S INTERACTION",
        "3.1 Teacher comes to the class on time and engages regularly",
        "3.2 Teacher maintains discipline in the class.",
        "3.3 Teacher offers assistance and counseling to the needy students.",
        "3.4 Teacher encourages students’ questioning and creativity",
        "3.5 Teacher is courteous and impartial in dealing with students"
    ]
    conn = sqlite3.connect('feedback.db')
    c = conn.cursor()
    c.execute("SELECT * FROM subjects WHERE user_id = ?", (user_id, ))
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
                    c.execute(
                        "INSERT INTO feedback (student_id, subject_id, criteria, rating, user_id) VALUES (?, ?, ?, ?, ?)",
                        (student_id, subj_id, crit, int(rating), user_id))
                    conn.commit()
                    conn.close()
        return redirect('/success')
    return render_template('feedback.html',
                           subjects=subjects,
                           criteria=criteria_list)


@app.route('/student_responses')
def student_responses():
    if 'user_id' not in session:
        return redirect('/login')
    user_id = session['user_id']

    conn = sqlite3.connect('feedback.db')
    c = conn.cursor()
    # Each row: (student_id, subject_name, criteria, rating)
    c.execute(
        '''
        SELECT student_id, subjects.name, criteria, rating
        FROM feedback
        JOIN subjects ON feedback.subject_id = subjects.id
        WHERE feedback.user_id = ?
        ORDER BY student_id, subject_id, criteria
    ''', (user_id, ))
    rows = c.fetchall()

    # How many unique students responded?
    c.execute(
        '''
        SELECT COUNT(DISTINCT student_id)
        FROM feedback
        WHERE user_id = ?
    ''', (user_id, ))
    num_students = c.fetchone()[0]
    conn.close()

    return render_template('student_responses.html',
                           rows=rows,
                           num_students=num_students)


@app.route('/download_student_responses')
def download_student_responses():
    if 'user_id' not in session:
        return redirect('/login')
    user_id = session['user_id']

    conn = sqlite3.connect('feedback.db')
    df = pd.read_sql_query('''
        SELECT student_id, subjects.name as subject, criteria, rating
        FROM feedback
        JOIN subjects ON feedback.subject_id = subjects.id
        WHERE feedback.user_id = ?
        ORDER BY student_id, subject, criteria
    ''',
                           conn,
                           params=(user_id, ))
    conn.close()

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Responses')
    output.seek(0)
    return send_file(output,
                     download_name="student's_response.xlsx",
                     as_attachment=True)


@app.route('/success')
def success():
    return render_template('success.html')


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
