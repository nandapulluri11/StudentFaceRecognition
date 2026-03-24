
import sqlite3
from werkzeug.security import generate_password_hash

def create_tables():
    """Creates the necessary database tables for the educational content management system."""
    conn = sqlite3.connect('educational_content.db')
    cursor = conn.cursor()

    # Departments table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS departments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    );
    """)

    # User table for students and faculty
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('student', 'faculty')),
        full_name TEXT,
        department_id INTEGER,
        FOREIGN KEY(department_id) REFERENCES departments(id)
    );
    """)

    # Course table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        faculty_id INTEGER NOT NULL,
        department_id INTEGER,
        FOREIGN KEY(faculty_id) REFERENCES users(id),
        FOREIGN KEY(department_id) REFERENCES departments(id)
    );
    """)

    # Course enrollment table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS course_enrollments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        FOREIGN KEY(student_id) REFERENCES users(id),
        FOREIGN KEY(course_id) REFERENCES courses(id),
        UNIQUE(student_id, course_id)
    );
    """)

    # Attendance table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('Present', 'Absent', 'Late')),
        marked_by INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY(student_id) REFERENCES users(id),
        FOREIGN KEY(course_id) REFERENCES courses(id),
        FOREIGN KEY(marked_by) REFERENCES users(id),
        UNIQUE(student_id, course_id, date)
    );
    """)

    # Course notes table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        file_path TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        upload_date TEXT NOT NULL,
        downloads_count INTEGER DEFAULT 0,
        download_enabled BOOLEAN NOT NULL DEFAULT 1,
        FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    """)

    # Assignments table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        due_date TEXT NOT NULL,
        max_file_size INTEGER DEFAULT 10485760, -- 10MB
        allowed_formats TEXT, -- e.g., "PDF,DOC,ZIP"
        late_submissions_policy TEXT,
        FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    """)

    # Submissions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        file_path TEXT NOT NULL,
        submission_date TEXT NOT NULL,
        grade TEXT,
        FOREIGN KEY(assignment_id) REFERENCES assignments(id),
        FOREIGN KEY(student_id) REFERENCES users(id),
        UNIQUE(assignment_id, student_id)
    );
    """)
    
    # Audit log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT NOT NULL,
        target_id INTEGER,
        target_type TEXT,
        timestamp TEXT NOT NULL,
        details TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)

    # Insert sample data if empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO departments (name) VALUES ('Computer Science'), ('Electrical Engineering'), ('Mechanical Engineering')")
        
        # Sample Users (Password is 'password' for all for testing)
        password_hash = generate_password_hash('password')
        cursor.execute("INSERT INTO users (username, password_hash, role, full_name, department_id) VALUES ('faculty1', ?, 'faculty', 'Dr. Smith', 1)", (password_hash,))
        cursor.execute("INSERT INTO users (username, password_hash, role, full_name, department_id) VALUES ('student1', ?, 'student', 'John Doe', 1)", (password_hash,))
        
        cursor.execute("INSERT INTO courses (name, description, faculty_id, department_id) VALUES ('Intro to AI', 'Foundations of Artificial Intelligence', 1, 1)")
        cursor.execute("INSERT INTO course_enrollments (student_id, course_id) VALUES (2, 1)")

    conn.commit()
    conn.close()
    print("Database tables updated successfully.")

if __name__ == "__main__":
    create_tables()
