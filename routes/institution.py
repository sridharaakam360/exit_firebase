from flask import Blueprint, render_template, redirect, url_for, flash, session, request, jsonify
from utils.db import get_db_connection
from utils.security import institute_admin_required, sanitize_input, super_admin_required
from forms import AddStudentForm
import logging
from mysql.connector import Error
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

institution_bp = Blueprint('institution', __name__)
logger = logging.getLogger(__name__)

@institution_bp.route('/dashboard')
@institute_admin_required
def institution_dashboard():
    logger.info(f"Rendering dashboard for user {session['username']} with role {session['role']}")
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('auth.institution_login'))
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        # For superadmin, redirect to admin dashboard
        if session['role'] == 'superadmin':
            return redirect(url_for('admin.admin_dashboard'))
            
        cursor.execute('''
            SELECT i.*, sp.name as plan_name, sp.description as plan_description, sp.is_active
            FROM institutions i
            LEFT JOIN subscription_plans sp ON i.subscription_plan_id = sp.id
            WHERE i.id = %s
        ''', (session['institution_id'],))
        institution = cursor.fetchone()
        
        if not institution:
            logger.error(f"Institution not found for ID: {session['institution_id']}")
            flash('Institution not found.', 'danger')
            return redirect(url_for('auth.institution_login'))
        
        cursor.execute('''
            SELECT COUNT(*) as student_count,
                   AVG(r.score / r.total_questions * 100) as avg_score,
                   COUNT(DISTINCT r.id) as quiz_count
            FROM users u
            JOIN institution_students ist ON u.id = ist.user_id
            LEFT JOIN results r ON u.id = r.user_id
            WHERE ist.institution_id = %s AND u.role = 'student'
        ''', (session['institution_id'],))
        stats = cursor.fetchone()
        
        cursor.execute('''
            SELECT u.username, r.score, r.total_questions, r.date_taken,
                   s.name as subject_name
            FROM users u
            JOIN institution_students ist ON u.id = ist.user_id
            LEFT JOIN results r ON u.id = r.user_id
            LEFT JOIN subjects s ON r.subject_id = s.id
            WHERE ist.institution_id = %s AND u.role = 'student'
            ORDER BY r.date_taken DESC
            LIMIT 5
        ''', (session['institution_id'],))
        recent_results = cursor.fetchall()
        
        stats['avg_score'] = round(stats['avg_score'], 1) if stats['avg_score'] else 0
        
        return render_template('institution/institution_dashboard.html',
                              institution=institution,
                              stats=stats,
                              recent_results=recent_results,
                              now=datetime.now())
    except Error as err:
        logger.error(f"Database error in institution dashboard: {str(err)}")
        flash('Error retrieving dashboard data.', 'danger')
        return render_template('institution/institution_dashboard.html',
                              institution=None,
                              stats={'student_count': 0, 'avg_score': 0, 'quiz_count': 0},
                              recent_results=[])
    finally:
        cursor.close()
        conn.close()

@institution_bp.route('/manage_students', methods=['GET', 'POST'])
@institute_admin_required
def manage_students():
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('institution.institution_dashboard'))
    
    cursor = conn.cursor(dictionary=True)
    try:
        # For superadmin, allow selecting institution
        is_superadmin = session['role'] == 'superadmin'
        selected_institution_id = request.args.get('institution_id', type=int)
        institution_list = None
        
        if is_superadmin:
            cursor.execute('SELECT id, name, institution_code FROM institutions ORDER BY name')
            institution_list = cursor.fetchall()
            
            if selected_institution_id:
                cursor.execute('SELECT institution_code FROM institutions WHERE id = %s', (selected_institution_id,))
                institution = cursor.fetchone()
            else:
                return render_template('institution/manage_students.html',
                                      institutions=institution_list,
                                      students=[],
                                      student_count=0,
                                      page=1,
                                      total_pages=0)
        else:
            selected_institution_id = session['institution_id']
            cursor.execute('SELECT institution_code FROM institutions WHERE id = %s', (selected_institution_id,))
            institution = cursor.fetchone()

        institution_code = institution['institution_code'] if institution else None

        form = AddStudentForm()
        if institution_code:
            form.institution_code.data = institution_code

        if request.method == 'POST' and form.validate_on_submit():
            username = sanitize_input(form.username.data)
            email = sanitize_input(form.email.data)
            password = generate_password_hash(form.password.data)
            
            cursor.execute('SELECT id FROM users WHERE username = %s OR email = %s', (username, email))
            if cursor.fetchone():
                flash('Username or email already exists.', 'danger')
            else:
                try:
                    conn.autocommit = False
                    cursor.execute('''
                        INSERT INTO users 
                        (username, email, password_hash, role, status, last_active)
                        VALUES (%s, %s, %s, %s, %s, NOW())
                    ''', (username, email, password, 'student', 'active'))
                    user_id = cursor.lastrowid
                    
                    cursor.execute('''
                        INSERT INTO institution_students 
                        (institution_id, user_id)
                        VALUES (%s, %s)
                    ''', (selected_institution_id, user_id))
                    
                    conn.commit()
                    flash('Student added successfully.', 'success')
                except Error as e:
                    conn.rollback()
                    logger.error(f"Database error adding student: {str(e)}")
                    flash('Error adding student.', 'danger')
                return redirect(url_for('institution.manage_students', institution_id=selected_institution_id))

        page = request.args.get('page', 1, type=int)
        per_page = 20
        offset = (page - 1) * per_page
        
        cursor.execute('''
            SELECT COUNT(*) as total 
            FROM users u
            JOIN institution_students ist ON u.id = ist.user_id
            WHERE ist.institution_id = %s AND u.role = "student"
        ''', (selected_institution_id,))
        student_count = cursor.fetchone()['total']
        total_pages = (student_count + per_page - 1) // per_page
        
        cursor.execute('''
            SELECT u.id, u.username, u.email, u.status, u.created_at, 
                   COUNT(r.id) as quiz_count,
                   AVG(r.score / r.total_questions * 100) as avg_score,
                   MAX(r.date_taken) as last_quiz_date,
                   u.last_active
            FROM users u
            JOIN institution_students ist ON u.id = ist.user_id
            LEFT JOIN results r ON u.id = r.user_id
            WHERE ist.institution_id = %s AND u.role = 'student'
            GROUP BY u.id
            ORDER BY u.username
            LIMIT %s OFFSET %s
        ''', (selected_institution_id, per_page, offset))
        students = cursor.fetchall()
        
        return render_template('institution/manage_students.html', 
                              students=students, 
                              student_count=student_count,
                              page=page,
                              total_pages=total_pages,
                              form=form,
                              institution_code=institution_code,
                              institutions=institution_list,
                              selected_institution_id=selected_institution_id)
    except Error as err:
        logger.error(f"Database error in manage_students: {str(err)}")
        flash('Error processing students.', 'danger')
        return redirect(url_for('institution.institution_dashboard'))
    finally:
        cursor.close()
        conn.close()

@institution_bp.route('/edit_student/<int:student_id>', methods=['GET', 'POST'])
@institute_admin_required
def edit_student(student_id):
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('institution.manage_students'))
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute('''
            SELECT u.* FROM users u 
            JOIN institution_students ist ON u.id = ist.user_id
            WHERE u.id = %s AND ist.institution_id = %s AND u.role = 'student'
        ''', (student_id, session['institution_id']))
        student = cursor.fetchone()
        
        if not student:
            flash('Student not found or not authorized.', 'danger')
            return redirect(url_for('institution.manage_students'))
        
        form = AddStudentForm()
        
        if request.method == 'GET':
            form.username.data = student['username']
            form.email.data = student['email']
            cursor.execute('SELECT institution_code FROM institutions WHERE id = %s', (session['institution_id'],))
            institution = cursor.fetchone()
            form.institution_code.data = institution['institution_code'] if institution else ''
            form.submit.label.text = 'Update Student'
        
        elif request.method == 'POST':
            logger.info(f"Form data: {request.form}")
            
            if form.validate_on_submit():
                username = sanitize_input(form.username.data)
                email = sanitize_input(form.email.data)
                password = form.password.data
                
                cursor.execute('SELECT id FROM users WHERE (username = %s OR email = %s) AND id != %s', 
                              (username, email, student_id))
                if cursor.fetchone():
                    flash('Username or email already exists for another user.', 'danger')
                else:
                    try:
                        conn.autocommit = False
                        if password:
                            password_hash = generate_password_hash(password)
                            cursor.execute('''
                                UPDATE users 
                                SET username = %s, email = %s, password_hash = %s, last_active = NOW()
                                WHERE id = %s
                            ''', (username, email, password_hash, student_id))
                        else:
                            cursor.execute('''
                                UPDATE users 
                                SET username = %s, email = %s, last_active = NOW()
                                WHERE id = %s
                            ''', (username, email, student_id))
                        
                        conn.commit()
                        flash('Student updated successfully.', 'success')
                        return redirect(url_for('institution.manage_students'))
                    except Error as err:
                        conn.rollback()
                        logger.error(f"Database error updating student: {str(err)}")
                        flash('Error updating student.', 'danger')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        flash(f"Error in {getattr(form, field).label.text}: {error}", 'danger')
                        logger.warning(f"Form field '{field}' error: {error}")
                
                logger.warning(f"Form validation failed: {form.errors}")
                if 'submit' not in request.form:
                    logger.warning("Form submit button not found in request data")
                    flash("Form submission error. Please try again.", 'danger')
        
        return render_template('institution/edit_student.html', form=form, student=student)
    
    except Error as err:
        logger.error(f"Database error in edit_student: {str(err)}")
        flash('Error retrieving student data.', 'danger')
        return redirect(url_for('institution.manage_students'))
    finally:
        cursor.close()
        conn.close()

@institution_bp.route('/delete_student/<int:student_id>', methods=['POST'])
@institute_admin_required
def delete_student(student_id):
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        if conn is None:
            flash('Database connection error.', 'danger')
            return redirect(url_for('institution.manage_students'))
        
        conn.autocommit = False
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('''
            SELECT ist.id FROM institution_students ist
            WHERE ist.user_id = %s AND ist.institution_id = %s
        ''', (student_id, session['institution_id']))
        
        if not cursor.fetchone():
            flash('Student not found or not part of your institution.', 'danger')
            return redirect(url_for('institution.manage_students'))
        
        cursor.execute('DELETE FROM question_reviews WHERE user_id = %s', (student_id,))
        cursor.execute('DELETE FROM results WHERE user_id = %s', (student_id,))
        cursor.execute('DELETE FROM subscription_history WHERE user_id = %s', (student_id,))
        cursor.execute('DELETE FROM institution_students WHERE user_id = %s', (student_id,))
        cursor.execute('DELETE FROM users WHERE id = %s', (student_id,))
        
        conn.commit()
        flash('Student deleted successfully.', 'success')
    
    except Error as err:
        conn.rollback()
        logger.error(f"Database error deleting student: {str(err)}")
        flash('Error deleting student. Please try again.', 'danger')
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    
    return redirect(url_for('institution.manage_students'))

@institution_bp.route('/student_details/<int:student_id>')
@institute_admin_required
def student_details(student_id):
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('institution.manage_students'))
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute('''
            SELECT u.*, DATE_FORMAT(u.created_at, '%d-%m-%Y') as join_date, 
                   DATE_FORMAT(u.last_active, '%d-%m-%Y %H:%i') as last_active_formatted
            FROM users u 
            JOIN institution_students ist ON u.id = ist.user_id
            WHERE u.id = %s AND ist.institution_id = %s AND u.role = 'student'
        ''', (student_id, session['institution_id']))
        student = cursor.fetchone()
        
        if not student:
            flash('Student not found or not authorized.', 'danger')
            return redirect(url_for('institution.manage_students'))
        
        cursor.execute('''
            SELECT r.*, 
                   s.name as subject_name, 
                   DATE_FORMAT(r.date_taken, '%d-%m-%Y %H:%i') as date_formatted,
                   ROUND((r.score / r.total_questions) * 100, 1) as percentage
            FROM results r
            LEFT JOIN subjects s ON r.subject_id = s.id
            WHERE r.user_id = %s
            ORDER BY r.date_taken DESC
        ''', (student_id,))
        results = cursor.fetchall()
        
        cursor.execute('''
            SELECT 
                COUNT(r.id) as total_quizzes,
                ROUND(AVG(r.score / r.total_questions * 100), 1) as avg_score,
                ROUND(AVG(r.time_taken), 0) as avg_time
            FROM results r
            WHERE r.user_id = %s
        ''', (student_id,))
        stats = cursor.fetchone()
        
        return render_template('institution/student_details.html', 
                              student=student, 
                              results=results, 
                              stats=stats)
    
    except Error as err:
        logger.error(f"Database error in student_details: {str(err)}")
        flash('Error retrieving student details.', 'danger')
        return redirect(url_for('institution.manage_students'))
    finally:
        cursor.close()
        conn.close()

@institution_bp.route('/bulk_add_students', methods=['GET', 'POST'])
@institute_admin_required
def bulk_add_students():
    if request.method == 'POST':
        conn = None
        cursor = None
        
        try:
            conn = get_db_connection()
            if conn is None:
                flash('Database connection error.', 'danger')
                return redirect(url_for('institution.manage_students'))
            
            conn.autocommit = False
            cursor = conn.cursor(dictionary=True)
            
            students_data = request.form.get('students_data', '')
            
            if not students_data:
                flash('No student data provided.', 'danger')
                return redirect(url_for('institution.bulk_add_students'))
            
            students = []
            successful_count = 0
            failed_count = 0
            errors = []
            
            for line_number, line in enumerate(students_data.strip().split('\n'), 1):
                if not line.strip():
                    continue
                    
                parts = [part.strip() for part in line.split(',')]
                
                if len(parts) != 3:
                    errors.append(f"Line {line_number}: Invalid format. Expected username,email,password")
                    failed_count += 1
                    continue
                
                username, email, password = parts
                
                if not username or not email or not password:
                    errors.append(f"Line {line_number}: Missing required data")
                    failed_count += 1
                    continue
                
                cursor.execute('SELECT id FROM users WHERE username = %s OR email = %s', (username, email))
                if cursor.fetchone():
                    errors.append(f"Line {line_number}: Username or email already exists")
                    failed_count += 1
                    continue
                
                students.append((username, email, password))
            
            institution_id = session['institution_id']
            
            for username, email, password in students:
                hashed_password = generate_password_hash(password)
                
                cursor.execute('''
                    INSERT INTO users 
                    (username, email, password_hash, role, status, last_active)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                ''', (username, email, hashed_password, 'student', 'active'))
                user_id = cursor.lastrowid
                
                cursor.execute('''
                    INSERT INTO institution_students 
                    (institution_id, user_id)
                    VALUES (%s, %s)
                ''', (institution_id, user_id))
                
                successful_count += 1
            
            if successful_count > 0:
                conn.commit()
                flash(f'Successfully added {successful_count} students.', 'success')
            
            if failed_count > 0:
                flash(f'Failed to add {failed_count} students. See details below.', 'warning')
                for error in errors:
                    flash(error, 'warning')
            
            if successful_count > 0:
                return redirect(url_for('institution.manage_students'))
            
        except Error as err:
            conn.rollback()
            logger.error(f"Database error in bulk_add_students: {str(err)}")
            flash('Error adding students.', 'danger')
        
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    conn = get_db_connection()
    institution_code = None
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute('SELECT institution_code FROM institutions WHERE id = %s', (session['institution_id'],))
            result = cursor.fetchone()
            if result:
                institution_code = result['institution_code']
        finally:
            cursor.close()
            conn.close()
    
    return render_template('institution/bulk_add_students.html', institution_code=institution_code)

@institution_bp.route('/toggle_student_status/<int:student_id>', methods=['POST'])
@institute_admin_required
def toggle_student_status(student_id):
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify(success=False, message='Database connection error')
        
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('''
            SELECT u.id, u.status FROM users u 
            JOIN institution_students ist ON u.id = ist.user_id
            WHERE u.id = %s AND ist.institution_id = %s AND u.role = 'student'
        ''', (student_id, session['institution_id']))
        student = cursor.fetchone()
        
        if not student:
            return jsonify(success=False, message='Student not found or not authorized')
        
        new_status = 'inactive' if student['status'] == 'active' else 'active'
        
        cursor.execute('UPDATE users SET status = %s WHERE id = %s',
                      (new_status, student_id))
        conn.commit()
        
        return jsonify(success=True, new_status=new_status, 
                       message=f"Student status changed to {new_status}")
    
    except Error as err:
        logger.error(f"Database error in toggle_student_status: {str(err)}")
        return jsonify(success=False, message='Database error occurred')
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@institution_bp.route('/add_institution', methods=['GET', 'POST'])
@super_admin_required
def add_institution():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        institution_code = request.form.get('institution_code')
        
        if not all([name, email, institution_code]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('institution.manage_institutions'))
        
        conn = get_db_connection()
        if conn is None:
            flash('Database connection error.', 'danger')
            return redirect(url_for('institution.manage_institutions'))
        
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute('SELECT id FROM institutions WHERE institution_code = %s', (institution_code,))
            if cursor.fetchone():
                flash('Institution code already exists.', 'danger')
                return redirect(url_for('institution.manage_institutions'))
            
            cursor.execute('SELECT id FROM institutions WHERE email = %s', (email,))
            if cursor.fetchone():
                flash('Email already exists.', 'danger')
                return redirect(url_for('institution.manage_institutions'))
            
            cursor.execute('''
                INSERT INTO institutions 
                (name, institution_code, email) VALUES (%s, %s, %s)
            ''', (name, institution_code, email))
            conn.commit()
            flash('Institution added successfully.', 'success')
            
        except Error as err:
            conn.rollback()
            logger.error(f"Database error in add_institution: {str(err)}")
            flash('Error adding institution.', 'danger')
        finally:
            cursor.close()
            conn.close()
        
        return redirect(url_for('institution.manage_institutions'))
    
    return render_template('institution/add_institution.html')

@institution_bp.route('/edit_institution/<int:institution_id>', methods=['GET', 'POST'])
@super_admin_required
def edit_institution(institution_id):
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('institution.manage_institutions'))
    
    cursor = conn.cursor(dictionary=True)
    try:
        if request.method == 'GET':
            cursor.execute('SELECT * FROM institutions WHERE id = %s', (institution_id,))
            institution = cursor.fetchone()
            if not institution:
                flash('Institution not found.', 'danger')
                return redirect(url_for('institution.manage_institutions'))
            return render_template('institution/edit_institution.html', institution=institution)
        
        elif request.method == 'POST':
            name = request.form.get('name')
            email = request.form.get('email')
            institution_code = request.form.get('institution_code')
            
            if not all([name, email, institution_code]):
                flash('All fields are required.', 'danger')
                return redirect(url_for('institution.edit_institution', institution_id=institution_id))
            
            cursor.execute('SELECT id FROM institutions WHERE institution_code = %s AND id != %s', 
                         (institution_code, institution_id))
            if cursor.fetchone():
                flash('Institution code already exists.', 'danger')
                return redirect(url_for('institution.edit_institution', institution_id=institution_id))
            
            cursor.execute('SELECT id FROM institutions WHERE email = %s AND id != %s', 
                         (email, institution_id))
            if cursor.fetchone():
                flash('Email already exists.', 'danger')
                return redirect(url_for('institution.edit_institution', institution_id=institution_id))
            
            cursor.execute('''
                UPDATE institutions 
                SET name = %s, institution_code = %s, email = %s 
                WHERE id = %s
            ''', (name, institution_code, email, institution_id))
            conn.commit()
            flash('Institution updated successfully.', 'success')
            return redirect(url_for('institution.manage_institutions'))
            
    except Error as err:
        conn.rollback()
        logger.error(f"Database error in edit_institution: {str(err)}")
        flash('Error updating institution.', 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('institution.manage_institutions'))

@institution_bp.route('/subscription')
@institute_admin_required
def institution_subscription():
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('institution.institution_dashboard'))
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute('''
            SELECT i.*, sp.name as plan_name, sp.description as plan_description,
                   sp.student_range, sp.custom_student_range, sp.degree_access
            FROM institutions i
            LEFT JOIN subscription_plans sp ON i.subscription_plan_id = sp.id
            WHERE i.id = %s
        ''', (session['institution_id'],))
        institution = cursor.fetchone()
        
        cursor.execute('''
            SELECT 
                COUNT(*) as total_students,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_students,
                SUM(CASE WHEN status = 'inactive' THEN 1 ELSE 0 END) as inactive_students
            FROM users u
            JOIN institution_students ist ON u.id = ist.user_id
            WHERE ist.institution_id = %s AND u.role = 'student'
        ''', (session['institution_id'],))
        stats = cursor.fetchone()
        
        if institution and institution['student_range']:
            stats['available_slots'] = max(0, institution['student_range'] - stats['total_students'])
        else:
            stats['available_slots'] = 0
        
        cursor.execute('''
            SELECT * FROM subscription_plans 
            WHERE is_institution = TRUE AND is_active = 1
            ORDER BY price
        ''')
        plans = cursor.fetchall()
        
        for plan in plans:
            if plan['degree_access'] == 'both':
                cursor.execute('SELECT id, name, degree_type FROM subjects')
            else:
                cursor.execute('SELECT id, name, degree_type FROM subjects WHERE degree_type = %s', 
                             (plan['degree_access'],))
            
            plan['subjects'] = cursor.fetchall()
            
            if institution and institution['subscription_plan_id'] == plan['id']:
                plan['is_active'] = True
                plan['expires_on'] = institution['subscription_end']
            else:
                plan['is_active'] = False
                plan['expires_on'] = None
        
        return render_template('institution/institution_subscription.html',
                              institution=institution,
                              plans=plans,
                              stats=stats,
                              now=datetime.now())
                            
    except Error as err:
        logger.error(f"Database error in institution subscription: {str(err)}")
        flash('Error loading subscription plans.', 'danger')
        return redirect(url_for('institution.institution_dashboard'))
    finally:
        cursor.close()
        conn.close()

@institution_bp.route('/subscribe/<int:plan_id>', methods=['GET', 'POST'])
@institute_admin_required
def institution_subscribe(plan_id):
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('institution.institution_subscription'))
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute('''
            SELECT * FROM subscription_plans 
            WHERE id = %s AND is_institution = TRUE AND is_active = 1
        ''', (plan_id,))
        plan = cursor.fetchone()
        
        if not plan:
            flash('The selected plan is not available or has been deactivated.', 'danger')
            return redirect(url_for('institution.institution_subscription'))
        
        cursor.execute('''
            SELECT COUNT(*) as total_students
            FROM users u
            JOIN institution_students ist ON u.id = ist.user_id
            WHERE ist.institution_id = %s AND u.role = 'student'
        ''', (session['institution_id'],))
        stats = cursor.fetchone()
        
        if request.method == 'POST':
            student_range = plan['student_range']
            if plan['custom_student_range']:
                custom_range = request.form.get('student_range', type=int)
                if custom_range and custom_range >= stats['total_students']:
                    student_range = custom_range
                else:
                    flash(f'Student range must be at least {stats["total_students"]} (current total students).', 'danger')
                    return redirect(url_for('institution.institution_subscribe', plan_id=plan_id))
            
            start_date = datetime.now()
            end_date = start_date + timedelta(days=plan['duration_months'] * 30)
            
            try:
                conn.autocommit = False
                
                cursor.execute('''
                    UPDATE institutions 
                    SET subscription_plan_id = %s,
                        subscription_start = %s,
                        subscription_end = %s,
                        student_range = %s
                    WHERE id = %s
                ''', (plan_id, start_date, end_date, student_range, session['institution_id']))
                
                cursor.execute('''
                    INSERT INTO subscription_history 
                    (user_id, subscription_plan_id, start_date, end_date, amount_paid, payment_method)
                    VALUES (%s, %s, %s, %s, %s, 'institution')
                ''', (session['user_id'], plan_id, start_date, end_date, plan['price']))
                
                conn.commit()
                flash('Subscription updated successfully!', 'success')
                return redirect(url_for('institution.institution_dashboard'))
                
            except Error as err:
                conn.rollback()
                logger.error(f"Database error in institution subscription: {str(err)}")
                flash('Error processing subscription.', 'danger')
                return redirect(url_for('institution.institution_subscription'))
        
        if plan['degree_access'] == 'both':
            cursor.execute('SELECT id, name, degree_type FROM subjects')
        else:
            cursor.execute('SELECT id, name, degree_type FROM subjects WHERE degree_type = %s', 
                         (plan['degree_access'],))
        
        plan['subjects'] = cursor.fetchall()
        
        return render_template('institution/institution_subscribe.html', 
                              plan=plan,
                              stats=stats)
        
    except Error as err:
        logger.error(f"Database error in institution subscription: {str(err)}")
        flash('Error processing subscription.', 'danger')
        return redirect(url_for('institution.institution_subscription'))
    finally:
        cursor.close()
        conn.close()

@institution_bp.route('/subscription_history')
@institute_admin_required
def institution_subscription_history():
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('institution.institution_dashboard'))
    
    cursor = conn.cursor(dictionary=True)
    try:
        logger.info(f"Fetching subscription history for user_id: {session['user_id']}, institution_id: {session['institution_id']}")
        
        cursor.execute('''
            SELECT 
                sh.id,
                sh.subscription_plan_id,
                sp.name as plan_name,
                sp.price,
                sp.duration_months,
                sp.student_range,
                sh.payment_method,
                sh.amount_paid,
                DATE_FORMAT(sh.start_date, '%d-%m-%Y') as start_date,
                DATE_FORMAT(sh.end_date, '%d-%m-%Y') as end_date,
                DATE_FORMAT(sh.created_at, '%d-%m-%Y %H:%i') as created_at,
                CASE 
                    WHEN sh.end_date < CURDATE() THEN 'expired'
                    WHEN i.subscription_plan_id = sh.subscription_plan_id THEN 'active'
                    ELSE 'inactive'
                END as current_status,
                sp.description,
                CASE 
                    WHEN i.subscription_plan_id = sh.subscription_plan_id THEN TRUE
                    ELSE FALSE
                END as is_active
            FROM subscription_history sh
            JOIN subscription_plans sp ON sh.subscription_plan_id = sp.id
            JOIN institutions i ON i.id = %s
            WHERE sh.user_id = %s
            ORDER BY sh.start_date DESC
        ''', (session['institution_id'], session['user_id']))
        
        history = cursor.fetchall()
        logger.info(f"Found {len(history)} subscription history records")
        
        cursor.execute('''
            SELECT 
                i.subscription_plan_id,
                sp.name as plan_name,
                sp.price,
                sp.duration_months,
                sp.student_range,
                i.student_range as actual_students,
                DATE_FORMAT(i.subscription_start, '%d-%m-%Y') as start_date,
                DATE_FORMAT(i.subscription_end, '%d-%m-%Y') as end_date,
                CASE 
                    WHEN i.subscription_end < CURDATE() THEN 'expired'
                    ELSE 'active'
                END as current_status
            FROM institutions i
            JOIN subscription_plans sp ON i.subscription_plan_id = sp.id
            WHERE i.id = %s
        ''', (session['institution_id'],))
        
        current_subscription = cursor.fetchone()
        logger.info(f"Current subscription: {current_subscription}")
        
        if not history and current_subscription:
            logger.info("Creating history entry from current subscription")
            cursor.execute('''
                INSERT INTO subscription_history 
                (user_id, subscription_plan_id, start_date, end_date, amount_paid, payment_method)
                VALUES (%s, %s, %s, %s, %s, 'institution')
            ''', (
                session['user_id'],
                current_subscription['subscription_plan_id'],
                datetime.strptime(current_subscription['start_date'], '%d-%m-%Y'),
                datetime.strptime(current_subscription['end_date'], '%d-%m-%Y'),
                current_subscription['price']
            ))
            conn.commit()
            
            cursor.execute('''
                SELECT 
                    sh.id,
                    sh.subscription_plan_id,
                    sp.name as plan_name,
                    sp.price,
                    sp.duration_months,
                    sp.student_range,
                    sh.payment_method,
                    sh.amount_paid,
                    DATE_FORMAT(sh.start_date, '%d-%m-%Y') as start_date,
                    DATE_FORMAT(sh.end_date, '%d-%m-%Y') as end_date,
                    DATE_FORMAT(sh.created_at, '%d-%m-%Y %H:%i') as created_at,
                    CASE 
                        WHEN sh.end_date < CURDATE() THEN 'expired'
                        WHEN i.subscription_plan_id = sh.subscription_plan_id THEN 'active'
                        ELSE 'inactive'
                    END as current_status,
                    sp.description,
                    CASE 
                        WHEN i.subscription_plan_id = sh.subscription_plan_id THEN TRUE
                        ELSE FALSE
                    END as is_active
                FROM subscription_history sh
                JOIN subscription_plans sp ON sh.subscription_plan_id = sp.id
                JOIN institutions i ON i.id = %s
                WHERE sh.user_id = %s
                ORDER BY sh.start_date DESC
            ''', (session['institution_id'], session['user_id']))
            history = cursor.fetchall()
        
        return render_template('institution/institution_subscription_history.html',
                              history=history,
                              current_subscription=current_subscription,
                              now=datetime.now())
                            
    except Error as err:
        logger.error(f"Database error in institution subscription history: {str(err)}")
        flash('Error loading subscription history.', 'danger')
        return redirect(url_for('institution.institution_dashboard'))
    finally:
        cursor.close()
        conn.close()

@institution_bp.route('/activate_subscription/<int:subscription_id>', methods=['POST'])
@institute_admin_required
def activate_subscription(subscription_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify(success=False, message='Database connection error')
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute('''
            SELECT sh.*, sp.student_range, sp.is_active
            FROM subscription_history sh
            JOIN subscription_plans sp ON sh.subscription_plan_id = sp.id
            WHERE sh.id = %s AND sh.user_id = %s
        ''', (subscription_id, session['user_id']))
        subscription = cursor.fetchone()
        
        if not subscription:
            return jsonify(success=False, message='Subscription not found')
        
        if not subscription['is_active']:
            return jsonify(success=False, message='Cannot activate a subscription for an inactive plan')
        
        start_date = datetime.now()
        end_date = subscription['end_date']
        
        cursor.execute('''
            UPDATE institutions 
            SET subscription_plan_id = %s,
                subscription_start = %s,
                subscription_end = %s,
                student_range = %s
            WHERE id = %s
        ''', (subscription['subscription_plan_id'], start_date, end_date, 
              subscription['student_range'], session['institution_id']))
        
        conn.commit()
        return jsonify(success=True, message='Subscription activated successfully')
        
    except Error as err:
        conn.rollback()
        logger.error(f"Database error activating subscription: {str(err)}")
        return jsonify(success=False, message='Error activating subscription')
    finally:
        cursor.close()
        conn.close()