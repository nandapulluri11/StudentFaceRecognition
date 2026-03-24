
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import pandas as pd
import io

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super-secret-dev-key')

# Configuration
UPLOAD_FOLDER = 'uploads'
NOTES_FOLDER = os.path.join(UPLOAD_FOLDER, 'course_notes')
SUBMISSIONS_FOLDER = os.path.join(UPLOAD_FOLDER, 'submissions')

for folder in [NOTES_FOLDER, SUBMISSIONS_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

def get_db_connection():
    conn = sqlite3.connect('educational_content.db')
    conn.row_factory = sqlite3.Row
    return conn

# Auth Decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('role') != role:
                flash(f"Access denied: {role} only.")
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Routes ---

@app.route('/')
def index():
    if 'user_id' in session:
        if session['role'] == 'faculty':
            return redirect(url_for('faculty_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        # In a real app, use check_password_hash
        # For our sample data, we'll allow 'password' directly if hash check fails (for dev only)
        if user and (check_password_hash(user['password_hash'], password) or password == 'password'):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['full_name'] = user['full_name']
            return redirect(url_for('index'))
        
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- Faculty Dashboard ---

@app.route('/faculty')
@login_required
@role_required('faculty')
def faculty_dashboard():
    conn = get_db_connection()
    # Stats for faculty
    courses = conn.execute('SELECT * FROM courses WHERE faculty_id = ?', (session['user_id'],)).fetchall()
    
    # Real-time analytics: Average attendance per course
    analytics = conn.execute("""
        SELECT c.name, 
               CAST(SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS FLOAT) / COUNT(a.id) * 100 as avg_attendance
        FROM courses c
        LEFT JOIN attendance a ON c.id = a.course_id
        WHERE c.faculty_id = ?
        GROUP BY c.id
    """, (session['user_id'],)).fetchall()
    
    conn.close()
    return render_template('faculty/dashboard.html', courses=courses, analytics=analytics)

@app.route('/faculty/attendance/<int:course_id>', methods=['GET', 'POST'])
@login_required
@role_required('faculty')
def manage_attendance(course_id):
    conn = get_db_connection()
    course = conn.execute('SELECT * FROM courses WHERE id = ?', (course_id,)).fetchone()
    
    if request.method == 'POST':
        # Bulk attendance marking
        date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
        for key, status in request.form.items():
            if key.startswith('status_'):
                student_id = key.split('_')[1]
                # Insert or update
                conn.execute("""
                    INSERT INTO attendance (student_id, course_id, date, status, marked_by, timestamp)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                    ON CONFLICT(student_id, course_id, date) DO UPDATE SET status=excluded.status
                """, (student_id, course_id, date, status, session['user_id']))
        conn.commit()
        flash('Attendance updated successfully')

    students = conn.execute("""
        SELECT u.* FROM users u
        JOIN course_enrollments ce ON u.id = ce.student_id
        WHERE ce.course_id = ?
    """, (course_id,)).fetchall()
    
    # Get attendance for specific date if provided
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    attendance_records = conn.execute("""
        SELECT student_id, status FROM attendance 
        WHERE course_id = ? AND date = ?
    """, (course_id, date)).fetchall()
    
    attendance_map = {r['student_id']: r['status'] for r in attendance_records}
    
    conn.close()
    return render_template('faculty/attendance.html', course=course, students=students, date=date, attendance_map=attendance_map)

@app.route('/faculty/report/export/<int:course_id>')
@login_required
@role_required('faculty')
def export_report(course_id):
    conn = get_db_connection()
    query = """
        SELECT u.full_name, a.date, a.status 
        FROM attendance a
        JOIN users u ON a.student_id = u.id
        WHERE a.course_id = ?
    """
    df = pd.read_sql_query(query, conn, params=(course_id,))
    conn.close()
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Attendance')
    output.seek(0)
    
    return send_file(output, download_name=f"attendance_report_course_{course_id}.xlsx", as_attachment=True)

# --- Student Dashboard ---

@app.route('/student')
@login_required
@role_required('student')
def student_dashboard():
    conn = get_db_connection()
    
    # Personalized stats
    stats = conn.execute("""
        SELECT 
            COUNT(id) as total,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present,
            SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent,
            SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) as late
        FROM attendance
        WHERE student_id = ?
    """, (session['user_id'],)).fetchone()
    
    # Attendance history
    history = conn.execute("""
        SELECT a.*, c.name as course_name 
        FROM attendance a
        JOIN courses c ON a.course_id = c.id
        WHERE a.student_id = ?
        ORDER BY a.date DESC
    """, (session['user_id'],)).fetchall()
    
    conn.close()
    return render_template('student/dashboard.html', stats=stats, history=history)

# --- Error Handling ---
@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
