from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, Response, current_app
from flask_socketio import emit
from utils.db import get_db_connection
from utils.security import super_admin_required
from forms import QuestionForm, BulkImportForm 
from datetime import datetime
from mysql.connector import Error
from io import TextIOWrapper, StringIO
import csv
from flask_login import login_required, current_user
from flask_wtf.csrf import validate_csrf, CSRFError
from functools import wraps
import json
import logging

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, template_folder='templates')

# Store SocketIO instance
admin_bp.socketio = None

def set_socketio(socketio, app):
    """Set the SocketIO instance for the blueprint."""
    admin_bp.socketio = socketio
    app.logger.info("SocketIO set for admin blueprint")

    @socketio.on('connect', namespace='/admin')
    def handle_connect():
        app.logger.info("Admin connected to /admin namespace")
        active_users = len(socketio.server.manager.rooms.get('/admin', {}).get(None, {}))
        socketio.emit('active_users', {'count': active_users}, namespace='/admin')

    @socketio.on('disconnect', namespace='/admin')
    def handle_disconnect(sid):
        app.logger.info(f"Admin disconnected from /admin namespace, sid: {sid}")
        active_users = len(socketio.server.manager.rooms.get('/admin', {}).get(None, {}))
        socketio.emit('active_users', {'count': active_users}, namespace='/admin')

# Custom decorator
def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not getattr(current_user, 'is_admin', False):
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('auth.choose_login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@login_required
@super_admin_required
def admin_dashboard():
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('index'))

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute('''
            SELECT role, COUNT(*) as count 
            FROM users 
            WHERE role != 'superadmin'
            GROUP BY role
        ''')
        user_counts = cursor.fetchall()

        cursor.execute('SELECT COUNT(*) as count FROM subjects')
        subjects_count = cursor.fetchone()['count']

        cursor.execute('SELECT COUNT(*) as count FROM questions')
        questions_count = cursor.fetchone()['count']

        return render_template('admin/dashboard.html',
                               user_counts=user_counts,
                               subjects_count=subjects_count,
                               questions_count=questions_count)
    except Error as err:
        current_app.logger.error(f"Error in admin_dashboard: {str(err)}")
        flash('Error loading dashboard.', 'danger')
        return redirect(url_for('index'))
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/manage_questions', methods=['GET', 'POST'])
@admin_bp.route('/manage_questions/<int:page>', methods=['GET', 'POST'])
@login_required
@super_admin_required
def manage_questions(page=1):
    conn = get_db_connection()
    if not conn:
        flash('Database connection failed.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
    
    cursor = conn.cursor(dictionary=True)
    question_form = QuestionForm()
    bulk_form = BulkImportForm()
    
    try:
        cursor.execute('SELECT id, name FROM subjects')
        subjects = cursor.fetchall()
        question_form.subject_id.choices = [(subject['id'], subject['name']) for subject in subjects]
        bulk_form.subject_id.choices = [(subject['id'], subject['name']) for subject in subjects]
        
        degree = request.args.get('degree', '')
        subject_id = request.args.get('subject_id', '')
        chapter = request.args.get('chapter', '')
        difficulty = request.args.get('difficulty', '')
        search_query = request.args.get('search_query', '')

        query = 'SELECT q.*, s.name as subject_name, s.degree_type FROM questions q JOIN subjects s ON q.subject_id = s.id WHERE 1=1'
        params = []

        if degree:
            query += ' AND s.degree_type = %s'
            params.append(degree.capitalize())
        if subject_id:
            query += ' AND q.subject_id = %s'
            params.append(subject_id)
        if chapter:
            query += ' AND q.chapter = %s'
            params.append(chapter)
        if difficulty:
            query += ' AND q.difficulty = %s'
            params.append(difficulty)
        if search_query:
            query += ' AND q.question LIKE %s'
            params.append(f'%{search_query}%')
        
        per_page = 10
        offset = (page - 1) * per_page
        
        cursor.execute(query + ' LIMIT %s OFFSET %s', params + [per_page, offset])
        questions = cursor.fetchall()
        
        cursor.execute('SELECT COUNT(*) as count FROM questions q WHERE 1=1' + query.split('WHERE 1=1')[1], params)
        total_questions = cursor.fetchone()['count']
        total_pages = (total_questions + per_page - 1) // per_page
        
        if request.method == 'POST' and question_form.validate_on_submit():
            action = question_form.form_action.data
            if action == 'single':
                cursor.execute('''
                    INSERT INTO questions (question, option_a, option_b, option_c, option_d, correct_answer, chapter, difficulty, subject_id, is_previous_year, previous_year, topics, explanation)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    question_form.question.data, question_form.option_a.data, question_form.option_b.data, question_form.option_c.data, question_form.option_d.data,
                    question_form.correct_answer.data, question_form.chapter.data, question_form.difficulty.data, question_form.subject_id.data,
                    question_form.is_previous_year.data, question_form.previous_year.data or None, json.dumps(question_form.topics.data.split(',')) if question_form.topics.data else '[]',
                    question_form.explanation.data
                ))
                conn.commit()
                flash('Question added successfully!', 'success')
                admin_bp.socketio.emit('update', {'action': 'add'}, namespace='/admin')
                return redirect(url_for('admin.manage_questions', page=page, degree=degree))
    
    except Exception as e:
        current_app.logger.error(f"Error in manage_questions: {str(e)}")
        flash('An error occurred while processing your request.', 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return render_template('admin/manage_questions.html', question_form=question_form, bulk_form=bulk_form, questions=questions, page=page, total_pages=total_pages,
                         degree=degree, subject_id=subject_id, chapter=chapter, difficulty=difficulty, search_query=search_query)

@admin_bp.route('/bulk_import_questions', methods=['POST'])
@login_required
@super_admin_required
def bulk_import_questions():
    conn = get_db_connection()
    if not conn:
        flash('Database connection failed.', 'danger')
        return redirect(url_for('admin.manage_questions'))
    
    cursor = conn.cursor(dictionary=True)
    form = BulkImportForm()
    
    try:
        cursor.execute('SELECT id, name FROM subjects')
        subjects = cursor.fetchall()
        form.subject_id.choices = [(subject['id'], subject['name']) for subject in subjects]
        
        if form.validate_on_submit():
            # Use the stored CSV content from the form
            if form.csv_content and form.csv_fieldnames:
                # Create a StringIO object from the stored content
                csv_data = StringIO(form.csv_content)
                csv_reader = csv.DictReader(csv_data)
                
                # Validate fieldnames
                required_fields = {'question', 'option_a', 'option_b', 'option_c', 'option_d', 
                                  'correct_answer', 'chapter', 'difficulty'}
                if not required_fields.issubset(form.csv_fieldnames):
                    missing_fields = required_fields - set(form.csv_fieldnames)
                    flash(f'CSV file is missing required fields: {", ".join(missing_fields)}.', 'danger')
                    return redirect(url_for('admin.manage_questions'))
                
                valid_subject_ids = {str(subject['id']) for subject in subjects}
                if str(form.subject_id.data) not in valid_subject_ids:
                    flash('Invalid subject selected.', 'danger')
                    return redirect(url_for('admin.manage_questions'))

                # Verify the subject's degree_type
                cursor.execute('SELECT degree_type FROM subjects WHERE id = %s', (form.subject_id.data,))
                subject = cursor.fetchone()
                if not subject:
                    flash('Selected subject does not exist.', 'danger')
                    return redirect(url_for('admin.manage_questions'))
                
                imported_count = 0
                for i, row in enumerate(csv_reader, start=1):
                    try:
                        # Convert previous_year: empty string to None, or ensure it's an integer
                        previous_year = row.get('previous_year')
                        if previous_year == '':
                            previous_year = None
                        elif previous_year is not None:
                            previous_year = int(previous_year)  # Ensure it's an integer

                        cursor.execute('''
                            INSERT INTO questions (question, option_a, option_b, option_c, option_d, 
                                                  correct_answer, chapter, difficulty, subject_id, 
                                                  is_previous_year, previous_year, topics, explanation)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ''', (
                            row['question'], row['option_a'], row['option_b'], row['option_c'], row['option_d'],
                            row['correct_answer'], row['chapter'], row['difficulty'],
                            form.subject_id.data,
                            row.get('is_previous_year', False) == '1',  # Convert to boolean
                            previous_year,
                            json.dumps(row.get('topics', '').split(',')) if row.get('topics') else '[]',
                            row.get('explanation', '')
                        ))
                        imported_count += 1
                    except Exception as e:
                        current_app.logger.error(f"Error importing CSV row {i}: {str(e)} - Row data: {row}")
                        continue
                
                conn.commit()
                flash(f'{imported_count} questions imported successfully!', 'success')
                admin_bp.socketio.emit('update', {'action': 'bulk_import', 'count': imported_count}, namespace='/admin')
            else:
                flash('Please upload a valid CSV file.', 'danger')
        else:
            current_app.logger.info(f"Bulk import form validation failed: {form.errors}")
            flash('Form validation failed: ' + str(form.errors), 'danger')
    
    except Exception as e:
        current_app.logger.error(f"Error in bulk_import_questions: {str(e)}")
        flash('An error occurred during bulk import.', 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin.manage_questions'))

@admin_bp.route('/download_sample_csv')
@super_admin_required
def download_sample_csv():
    current_app.logger.debug("Generating sample CSV")
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=['question', 'option_a', 'option_b', 'option_c', 'option_d', 
                                               'correct_answer', 'chapter', 'difficulty', 'topics', 
                                               'is_previous_year', 'previous_year', 'explanation'])
    writer.writeheader()
    writer.writerow({
        'question': "What is the primary source of energy for Earth's climate system?",
        'option_a': 'The Sun',
        'option_b': 'Geothermal energy',
        'option_c': 'Nuclear energy',
        'option_d': 'Wind energy',
        'correct_answer': 'A',
        'chapter': 'Environmental Science',
        'difficulty': 'easy',
        'topics': 'climate, energy',
        'is_previous_year': '0',
        'previous_year': '',  # Empty for non-previous-year questions
        'explanation': "The Sun provides the primary energy for Earth's climate system through solar radiation."
    })
    writer.writerow({
        'question': 'Which drug is used to treat hypertension?',
        'option_a': 'Aspirin',
        'option_b': 'Lisinopril',
        'option_c': 'Ibuprofen',
        'option_d': 'Paracetamol',
        'correct_answer': 'B',
        'chapter': 'Pharmacology',
        'difficulty': 'medium',
        'topics': 'hypertension, drugs',
        'is_previous_year': '1',
        'previous_year': '2023',  # Valid integer for previous-year questions
        'explanation': 'Lisinopril is an ACE inhibitor used to treat hypertension.'
    })
    output.seek(0)
    current_app.logger.debug("Sample CSV generated, sending response")
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=sample_questions.csv'}
    )

@admin_bp.route('/edit_question/<int:question_id>', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit_question(question_id):
    conn = get_db_connection()
    if not conn:
        flash('Database connection failed.', 'danger')
        return redirect(url_for('admin.manage_questions'))
    
    cursor = conn.cursor(dictionary=True)
    form = QuestionForm()
    
    try:
        cursor.execute('SELECT id, name FROM subjects')
        subjects = cursor.fetchall()
        form.subject_id.choices = [(subject['id'], subject['name']) for subject in subjects]
        
        cursor.execute('SELECT q.*, s.degree_type FROM questions q JOIN subjects s ON q.subject_id = s.id WHERE q.id = %s', (question_id,))
        question = cursor.fetchone()
        
        if not question:
            flash('Question not found.', 'danger')
            return redirect(url_for('admin.manage_questions'))
        
        if request.method == 'GET':
            form.question.data = question['question']
            form.option_a.data = question['option_a']
            form.option_b.data = question['option_b']
            form.option_c.data = question['option_c']
            form.option_d.data = question['option_d']
            form.correct_answer.data = question['correct_answer']
            form.chapter.data = question['chapter']
            form.difficulty.data = question['difficulty']
            form.subject_id.data = question['subject_id']
            form.is_previous_year.data = question['is_previous_year']
            form.previous_year.data = question['previous_year']
            form.topics.data = ','.join(json.loads(question['topics'])) if question['topics'] else ''
            form.explanation.data = question['explanation']                                                                                 
        
        if request.method == 'POST' and form.validate_on_submit():
            cursor.execute('''
                UPDATE questions
                SET question = %s, option_a = %s, option_b = %s, option_c = %s, option_d = %s,
                    correct_answer = %s, chapter = %s, difficulty = %s, subject_id = %s,
                    is_previous_year = %s, previous_year = %s, topics = %s, explanation = %s
                WHERE id = %s
            ''', (
                form.question.data, form.option_a.data, form.option_b.data, form.option_c.data, form.option_d.data,
                form.correct_answer.data, form.chapter.data, form.difficulty.data, form.subject_id.data,
                form.is_previous_year.data, form.previous_year.data or None,
                json.dumps(form.topics.data.split(',')) if form.topics.data else '[]',
                form.explanation.data, question_id
            ))
            conn.commit()
            flash('Question updated successfully!', 'success')
            admin_bp.socketio.emit('update', {'action': 'edit', 'question_id': question_id}, namespace='/admin')
            # Fetch the degree_type of the selected subject for redirect
            cursor.execute('SELECT degree_type FROM subjects WHERE id = %s', (form.subject_id.data,))
            subject = cursor.fetchone()
            degree = subject['degree_type'].lower() if subject else ''
            return redirect(url_for('admin.manage_questions', degree=degree))
    
    except Exception as e:
        current_app.logger.error(f"Error in edit_question: {str(e)}")
        flash('An error occurred while editing the question.', 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return render_template('admin/edit_question.html', form=form, question_id=question_id, degree=question['degree_type'].lower())

@admin_bp.route('/delete_question/<int:question_id>', methods=['POST'])
@login_required
@super_admin_required
def delete_question(question_id):
    conn = get_db_connection()
    if not conn:
        flash('Database connection failed.', 'danger')
        return redirect(url_for('admin.manage_questions'))
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT s.degree_type FROM questions q JOIN subjects s ON q.subject_id = s.id WHERE q.id = %s', (question_id,))
        question = cursor.fetchone()
        if not question:
            flash('Question not found.', 'danger')
            return redirect(url_for('admin.manage_questions'))

        cursor.execute('DELETE FROM questions WHERE id = %s', (question_id,))
        conn.commit()
        flash('Question deleted successfully!', 'success')
        admin_bp.socketio.emit('update', {'action': 'delete', 'question_id': question_id}, namespace='/admin')
        return redirect(url_for('admin.manage_questions', degree=question['degree_type'].lower()))
    
    except Exception as e:
        current_app.logger.error(f"Error in delete_question: {str(e)}")
        flash('An error occurred while deleting the question.', 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin.manage_questions'))

@admin_bp.route('/subjects/<degree>')
@login_required
@super_admin_required
def get_subjects(degree):
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        if degree.lower() == 'all':
            cursor.execute('SELECT id, name, degree_type FROM subjects')
            subjects = cursor.fetchall()
        else:
            # Capitalize degree to match database values (e.g., 'bpharm' -> 'Bpharm')
            degree = degree.capitalize()
            cursor.execute('SELECT id, name, degree_type FROM subjects WHERE degree_type = %s', (degree,))
            subjects = cursor.fetchall()
        return jsonify(subjects)
    except Exception as e:
        current_app.logger.error(f"Error in get_subjects: {str(e)}")
        return jsonify({'error': 'Failed to fetch subjects'}), 500
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/manage_users', methods=['GET', 'POST'])
@admin_required
def manage_users():
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
    
    cursor = conn.cursor(dictionary=True)
    try:
        page = request.args.get('page', 1, type=int)
        user_type = request.args.get('type', 'all')
        per_page = 20
        offset = (page - 1) * per_page
        
        cursor.execute('''
            SELECT role, COUNT(*) as count, MAX(last_active) as last_active
            FROM users 
            WHERE role != 'superadmin'
            GROUP BY role
        ''')
        user_counts = {row['role']: {'count': row['count'], 'last_active': row['last_active']} for row in cursor.fetchall()}
        
        if user_type == 'all':
            where_clause = 'u.role != "superadmin"'
        else:
            where_clause = f'u.role = "{user_type}"'
        
        cursor.execute(f'SELECT COUNT(*) as total FROM users u WHERE {where_clause}')
        total_users = cursor.fetchone()['total']
        total_pages = (total_users + per_page - 1) // per_page
        
        if user_type == 'instituteadmin':
            cursor.execute(f'''
                SELECT u.*, sp.name as plan_name, i.name as institution_name, i.institution_code, u.last_active
                FROM users u 
                LEFT JOIN subscription_plans sp ON u.subscription_plan_id = sp.id 
                JOIN institutions i ON u.id = i.admin_id
                WHERE {where_clause}
                ORDER BY u.created_at DESC
                LIMIT %s OFFSET %s
            ''', (per_page, offset))
        elif user_type == 'student':
            cursor.execute(f'''
                SELECT u.*, sp.name as plan_name, i.name as institution_name, i.institution_code, u.last_active
                FROM users u 
                LEFT JOIN subscription_plans sp ON u.subscription_plan_id = sp.id 
                JOIN institution_students is_rel ON u.id = is_rel.user_id
                JOIN institutions i ON is_rel.institution_id = i.id
                WHERE {where_clause}
                ORDER BY u.created_at DESC
                LIMIT %s OFFSET %s
            ''', (per_page, offset))
        else:
            cursor.execute(f'''
                SELECT u.*, sp.name as plan_name, i.name as institution_name, i.institution_code, u.last_active
                FROM users u 
                LEFT JOIN subscription_plans sp ON u.subscription_plan_id = sp.id 
                LEFT JOIN institution_students is_rel ON u.id = is_rel.user_id
                LEFT JOIN institutions i ON is_rel.institution_id = i.id
                WHERE {where_clause}
                ORDER BY u.created_at DESC
                LIMIT %s OFFSET %s
            ''', (per_page, offset))
        users = cursor.fetchall()
        
        return render_template('admin/manage_users.html', 
                             users=users,
                             page=page,
                             total_pages=total_pages,
                             total_users=total_users,
                             user_type=user_type,
                             user_counts=user_counts)
    except Error as err:
        current_app.logger.error(f"Database error in manage_users: {str(err)}")
        flash('Error retrieving users.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/add_user', methods=['GET', 'POST'])
@admin_required
def add_user():
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('admin.manage_users'))
    
    cursor = conn.cursor(dictionary=True)
    form = UserForm()
    
    try:
        if request.method == 'POST' and form.validate_on_submit():
            cursor.execute('SELECT id FROM users WHERE username = %s OR email = %s', 
                          (form.username.data, form.email.data))
            if cursor.fetchone():
                flash('Username or email already exists.', 'danger')
                return redirect(url_for('admin.add_user'))
            
            password_hash = generate_password_hash(form.password.data)
            
            cursor.execute('''
                INSERT INTO users (username, email, password, role, status)
                VALUES (%s, %s, %s, %s, %s)
            ''', (form.username.data, form.email.data, password_hash, form.role.data, form.status.data))
            user_id = cursor.lastrowid
            
            if form.role.data == 'student':
                institute_code = request.form.get('institute_code')
                if not institute_code:
                    conn.rollback()
                    flash('Institute code is required for student users.', 'danger')
                    return redirect(url_for('admin.add_user'))
                
                cursor.execute('SELECT id FROM institutions WHERE institution_code = %s', (institute_code,))
                institution = cursor.fetchone()
                if not institution:
                    conn.rollback()
                    flash('Invalid institute code.', 'danger')
                    return redirect(url_for('admin.add_user'))
                institution_id = institution['id']
                
                cursor.execute('''
                    INSERT INTO institution_students (institution_id, user_id)
                    VALUES (%s, %s)
                ''', (institution_id, user_id))
            
            if form.role.data == 'instituteadmin':
                institute_name = request.form.get('institute_name')
                institute_code = request.form.get('institute_code_admin')
                
                if not institute_name or not institute_code:
                    conn.rollback()
                    flash('Institute name and code are required for institute admin.', 'danger')
                    return redirect(url_for('admin.add_user'))
                
                cursor.execute('SELECT id FROM institutions WHERE institution_code = %s', (institute_code,))
                if cursor.fetchone():
                    conn.rollback()
                    flash('Institution code already exists.', 'danger')
                    return redirect(url_for('admin.add_user'))
                
                cursor.execute('''
                    INSERT INTO institutions (name, institution_code, admin_id, email)
                    VALUES (%s, %s, %s, %s)
                ''', (institute_name, institute_code, user_id, form.email.data))
            
            conn.commit()
            flash('User added successfully.', 'success')
            return redirect(url_for('admin.manage_users'))
        else:
            if request.method == 'POST':
                current_app.logger.error(f"Form validation failed: {form.errors}")
                flash('Please correct the errors in the form.', 'danger')
        
        return render_template('admin/add_user.html', form=form)
    except Error as err:
        conn.rollback()
        current_app.logger.error(f"Database error in add_user: {str(err)}")
        flash('Error adding user.', 'danger')
        return redirect(url_for('admin.manage_users'))
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('admin.manage_users'))
    
    cursor = conn.cursor(dictionary=True)
    try:
        form = UserForm()
        if request.method == 'GET':
            cursor.execute('''
                SELECT u.*, i.name as institution_name, i.institution_code
                FROM users u
                LEFT JOIN institution_students is_rel ON u.id = is_rel.user_id
                LEFT JOIN institutions i ON is_rel.institution_id = i.id
                WHERE u.id = %s
            ''', (user_id,))
            user = cursor.fetchone()
            
            if not user:
                flash('User not found.', 'danger')
                return redirect(url_for('admin.manage_users'))
            
            form.username.data = user['username']
            form.email.data = user['email']
            form.role.data = user['role']
            form.status.data = user['status']
        
        if request.method == 'POST' and form.validate_on_submit():
            if form.password.data:
                password_hash = generate_password_hash(form.password.data)
                cursor.execute('''
                    UPDATE users 
                    SET username = %s, email = %s, password = %s, role = %s, status = %s
                    WHERE id = %s
                ''', (form.username.data, form.email.data, password_hash, form.role.data, form.status.data, user_id))
            else:
                cursor.execute('''
                    UPDATE users 
                    SET username = %s, email = %s, role = %s, status = %s
                    WHERE id = %s
                ''', (form.username.data, form.email.data, form.role.data, form.status.data, user_id))
            
            if form.role.data == 'student':
                institute_code = request.form.get('institute_code')
                if institute_code:
                    cursor.execute('SELECT id FROM institutions WHERE institution_code = %s', (institute_code,))
                    institution = cursor.fetchone()
                    
                    if institution:
                        cursor.execute('''
                            SELECT id FROM institution_students 
                            WHERE user_id = %s
                        ''', (user_id,))
                        existing = cursor.fetchone()
                        
                        if existing:
                            cursor.execute('''
                                UPDATE institution_students 
                                SET institution_id = %s 
                                WHERE user_id = %s
                            ''', (institution['id'], user_id))
                        else:
                            cursor.execute('''
                                INSERT INTO institution_students (institution_id, user_id)
                                VALUES (%s, %s)
                            ''', (institution['id'], user_id))
                    else:
                        flash('Invalid institute code. Student will not be linked to any institution.', 'warning')
                else:
                    cursor.execute('DELETE FROM institution_students WHERE user_id = %s', (user_id,))
            
            conn.commit()
            flash('User updated successfully.', 'success')
            return redirect(url_for('admin.manage_users'))
        
        return render_template('admin/edit_user.html', form=form, user_id=user_id, is_edit=True)
    except Error as err:
        conn.rollback()
        current_app.logger.error(f"Database error in edit_user: {str(err)}")
        flash('Error updating user.', 'danger')
        return redirect(url_for('admin.manage_users'))
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/delete_user/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('admin.manage_users'))
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute('SELECT id FROM institutions WHERE admin_id = %s', (user_id,))
        institution = cursor.fetchone()
        
        if institution:
            flash('Cannot delete user because they are an admin of an institution.', 'danger')
            return redirect(url_for('admin.manage_users'))

        cursor.execute('DELETE FROM users WHERE id = %s AND role != "superadmin"', (user_id,))
        conn.commit()
        flash('User deleted successfully.', 'success')
        return redirect(url_for('admin.manage_users'))
    except Error as err:
        conn.rollback()
        current_app.logger.error(f"Database error in delete_user: {str(err)}")
        flash('Error deleting user.', 'danger')
        return redirect(url_for('admin.manage_users'))
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/manage_content', methods=['GET', 'POST'])
@admin_required
def manage_content():
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('auth.choose_login'))
    
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT id, name, price, duration_months AS duration, degree_access,
                   is_institution, student_range, includes_previous_years,
                   description, is_active
            FROM subscription_plans
            ORDER BY is_institution, name
        """)
        plans = cursor.fetchall()
        
        cursor.execute("""
            SELECT id, username, email, subscription_plan_id, subscription_status
            FROM users
        """)
        users = cursor.fetchall()
        
        cursor.execute("""
            SELECT id, name, email, subscription_plan_id, subscription_end
            FROM institutions
        """)
        institutions = cursor.fetchall()
        
        for inst in institutions:
            if inst['subscription_end']:
                inst['subscription_end'] = inst['subscription_end'].date()
        
        for plan in plans:
            plan['user_count'] = sum(1 for user in users if user['subscription_plan_id'] == plan['id'] and user['subscription_status'] == 'active')
            plan['inst_count'] = sum(1 for inst in institutions if inst['subscription_plan_id'] == plan['id'] and inst['subscription_end'] and inst['subscription_end'] >= datetime.now().date())
        
        cursor.execute("""
            SELECT id, name, degree_type, description
            FROM subjects
            ORDER BY name
        """)
        subjects = cursor.fetchall()
        
        return render_template('admin/manage_content.html',
                             plans=plans,
                             subjects=subjects,
                             users=users,
                             institutions=institutions,
                             has_degree_type=True,
                             now=datetime.now().date())
        
    except Exception as e:
        if conn and conn.in_transaction:
            conn.rollback()
        current_app.logger.error(f"Error in manage_content: {str(e)}")
        flash('An error occurred while managing content', 'error')
        return redirect(url_for('auth.choose_login'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@admin_bp.route('/add_subject', methods=['POST'])
@admin_required
def add_subject():
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin.manage_content'))
    
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        
        subject_name = request.form.get('subject_name')
        degree_type = request.form.get('degree_type')
        description = request.form.get('description', '')
        
        if not subject_name:
            flash('Subject name is required', 'error')
            return redirect(url_for('admin.manage_content'))
        if not degree_type or degree_type not in ['Dpharm', 'Bpharm']:
            flash('Valid degree type is required', 'error')
            return redirect(url_for('admin.manage_content'))
        
        cursor.execute("SELECT id FROM subjects WHERE name = %s", (subject_name,))
        if cursor.fetchone():
            flash('A subject with this name already exists', 'error')
            return redirect(url_for('admin.manage_content'))
        
        cursor.execute("""
            INSERT INTO subjects (name, degree_type, description)
            VALUES (%s, %s, %s)
        """, (subject_name, degree_type, description))
        
        conn.commit()
        flash('Subject added successfully', 'success')
        current_app.logger.info(f"Admin {current_user.username} added subject: {subject_name}")
        return redirect(url_for('admin.manage_content'))
        
    except Exception as e:
        if conn and conn.in_transaction:
            conn.rollback()
        current_app.logger.error(f"Error in add_subject: {str(e)}")
        flash('An error occurred while adding the subject', 'error')
        return redirect(url_for('admin.manage_content'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@admin_bp.route('/edit_subject/<int:subject_id>', methods=['GET', 'POST'])
@admin_required
def edit_subject(subject_id):
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin.manage_content'))
    
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        
        if request.method == 'POST':
            subject_name = request.form.get('subject_name')
            degree_type = request.form.get('degree_type')
            description = request.form.get('description', '')
            
            if not subject_name:
                flash('Subject name is required', 'error')
                return redirect(url_for('admin.manage_content'))
            if not degree_type or degree_type not in ['Dpharm', 'Bpharm']:
                flash('Valid degree type is required', 'error')
                return redirect(url_for('admin.manage_content'))
            
            cursor.execute("SELECT id FROM subjects WHERE name = %s AND id != %s", (subject_name, subject_id))
            if cursor.fetchone():
                flash('A subject with this name already exists', 'error')
                return redirect(url_for('admin.manage_content'))
            
            cursor.execute("""
                UPDATE subjects
                SET name = %s, degree_type = %s, description = %s
                WHERE id = %s
            """, (subject_name, degree_type, description, subject_id))
            
            conn.commit()
            flash('Subject updated successfully', 'success')
            current_app.logger.info(f"Admin {current_user.username} updated subject ID: {subject_id}, new name: {subject_name}")
            return redirect(url_for('admin.manage_content'))
        
        cursor.execute("SELECT id, name, degree_type, description FROM subjects WHERE id = %s", (subject_id,))
        subject = cursor.fetchone()
        if not subject:
            flash('Subject not found', 'error')
            return redirect(url_for('admin.manage_content'))
        
        return render_template('admin/edit_subject.html', subject=subject)
        
    except Exception as e:
        if conn and conn.in_transaction:
            conn.rollback()
        current_app.logger.error(f"Error in edit_subject: {str(e)}")
        flash('An error occurred while editing the subject', 'error')
        return redirect(url_for('admin.manage_content'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@admin_bp.route('/delete_subject/<int:subject_id>', methods=['POST'])
@admin_required
def delete_subject(subject_id):
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin.manage_content'))
    
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id, name FROM subjects WHERE id = %s", (subject_id,))
        subject = cursor.fetchone()
        if not subject:
            flash('Subject not found', 'error')
            return redirect(url_for('admin.manage_content'))
        
        cursor.execute("DELETE FROM subjects WHERE id = %s", (subject_id,))
        conn.commit()
        
        flash(f"Subject '{subject['name']}' deleted successfully", 'success')
        current_app.logger.info(f"Admin {current_user.username} deleted subject ID: {subject_id}")
        return redirect(url_for('admin.manage_content'))
        
    except Exception as e:
        if conn and conn.in_transaction:
            conn.rollback()
        current_app.logger.error(f"Error in delete_subject: {str(e)}")
        flash('An error occurred while deleting the subject', 'error')
        return redirect(url_for('admin.manage_content'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@admin_bp.route('/add_plan', methods=['POST'])
@admin_required
def add_plan():
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin.manage_content'))
    
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        
        plan_name = request.form.get('plan_name')
        price = float(request.form.get('price', 0))
        duration = int(request.form.get('duration', 0))
        degree_access = request.form.get('degree_access')
        description = request.form.get('description', '')
        includes_previous_years = 1 if request.form.get('includes_previous_years') else 0
        is_institution = 1 if request.form.get('is_institution') else 0
        student_range = int(request.form.get('student_range', 0)) if is_institution else None
        
        if not plan_name:
            flash('Plan name is required', 'error')
            return redirect(url_for('admin.manage_content'))
        if price < 0:
            flash('Price must be a positive number', 'error')
            return redirect(url_for('admin.manage_content'))
        if duration < 1:
            flash('Duration must be at least 1 month', 'error')
            return redirect(url_for('admin.manage_content'))
        if degree_access not in ['Dpharm', 'Bpharm', 'both']:
            flash('Invalid degree access selection', 'error')
            return redirect(url_for('admin.manage_content'))
        if is_institution and (not student_range or student_range < 1):
            flash('Student limit must be a positive number for institutional plans', 'error')
            return redirect(url_for('admin.manage_content'))
        
        cursor.execute("SELECT id FROM subscription_plans WHERE name = %s", (plan_name,))
        if cursor.fetchone():
            flash('A plan with this name already exists', 'error')
            return redirect(url_for('admin.manage_content'))
        
        cursor.execute("""
            INSERT INTO subscription_plans (
                name, price, duration_months, degree_access,
                is_institution, student_range, includes_previous_years,
                description, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            plan_name, price, duration, degree_access,
            is_institution, student_range, includes_previous_years,
            description, 1
        ))
        
        conn.commit()
        flash('Subscription plan added successfully', 'success')
        current_app.logger.info(f"Admin {current_user.username} added new plan: {plan_name}")
        return redirect(url_for('admin.manage_content'))
        
    except Exception as e:
        if conn and conn.in_transaction:
            conn.rollback()
        current_app.logger.error(f"Error in add_plan: {str(e)}")
        flash('An error occurred while adding the plan', 'error')
        return redirect(url_for('admin.manage_content'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@admin_bp.route('/edit_plan/<int:plan_id>', methods=['GET', 'POST'])
@admin_required
def edit_plan(plan_id):
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin.manage_content'))

    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        
        if request.method == 'POST':
            name = request.form.get('plan_name')
            price = request.form.get('price')
            duration = request.form.get('duration')
            degree_access = request.form.get('degree_access')
            description = request.form.get('description', '')
            includes_previous_years = 1 if request.form.get('includes_previous_years') else 0
            is_institution = 1 if request.form.get('is_institution') else 0
            student_range = request.form.get('student_range')
            
            if not all([name, price, duration, degree_access]):
                flash('Name, price, duration, and degree access are required', 'error')
                return redirect(url_for('admin.edit_plan', plan_id=plan_id))
            
            try:
                price = float(price)
                if price < 0:
                    flash('Price must be a positive number', 'error')
                    return redirect(url_for('admin.edit_plan', plan_id=plan_id))
            except ValueError:
                flash('Price must be a valid number', 'error')
                return redirect(url_for('admin.edit_plan', plan_id=plan_id))
            
            try:
                duration = int(duration)
                if duration < 1:
                    flash('Duration must be at least 1 month', 'error')
                    return redirect(url_for('admin.edit_plan', plan_id=plan_id))
            except ValueError:
                flash('Duration must be a valid integer', 'error')
                return redirect(url_for('admin.edit_plan', plan_id=plan_id))
            
            if degree_access not in ['Dpharm', 'Bpharm', 'both']:
                flash('Invalid degree access selection', 'error')
                return redirect(url_for('admin.edit_plan', plan_id=plan_id))
            
            if is_institution:
                try:
                    student_range = int(student_range) if student_range else None
                    if student_range is None or student_range < 1:
                        flash('Student limit must be a positive number', 'error')
                        return redirect(url_for('admin.edit_plan', plan_id=plan_id))
                except ValueError:
                    flash('Student limit must be a valid integer', 'error')
                    return redirect(url_for('admin.edit_plan', plan_id=plan_id))
            else:
                student_range = None
            
            cursor.execute("""
                SELECT id FROM subscription_plans 
                WHERE name = %s AND id != %s
            """, (name, plan_id))
            existing_plan = cursor.fetchone()
            
            if existing_plan:
                flash('A plan with this name already exists', 'error')
                return redirect(url_for('admin.edit_plan', plan_id=plan_id))
            
            cursor.execute("""
                UPDATE subscription_plans 
                SET name = %s, price = %s, duration_months = %s, degree_access = %s,
                    description = %s, includes_previous_years = %s, is_institution = %s,
                    student_range = %s
                WHERE id = %s
            """, (name, price, duration, degree_access, description, includes_previous_years,
                  is_institution, student_range, plan_id))
            
            conn.commit()
            flash('Plan updated successfully', 'success')
            current_app.logger.info(f"Admin {current_user.username} updated plan ID: {plan_id}, new name: {name}")
            return redirect(url_for('admin.manage_content'))

        cursor.execute("""
            SELECT id, name, price, duration_months as duration, degree_access,
                   description, includes_previous_years, is_institution,
                   student_range
            FROM subscription_plans
            WHERE id = %s
        """, (plan_id,))
        plan = cursor.fetchone()
        
        if not plan:
            flash('Plan not found', 'error')
            return redirect(url_for('admin.manage_content'))
        
        return render_template('admin/edit_plan.html', plan=plan)
        
    except Exception as e:
        if conn and conn.in_transaction:
            conn.rollback()
        current_app.logger.error(f"Error in edit_plan: {str(e)}")
        flash('An error occurred while updating the plan', 'error')
        return redirect(url_for('admin.manage_content'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@admin_bp.route('/delete_plan/<int:plan_id>', methods=['POST'])
@admin_required
def delete_plan(plan_id):
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin.manage_content'))
    
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT id, name, is_institution, is_active
            FROM subscription_plans
            WHERE id = %s
        """, (plan_id,))
        plan = cursor.fetchone()
        
        if not plan:
            flash('Plan not found', 'error')
            return redirect(url_for('admin.manage_content'))
        
        default_individual_plan_id = 1
        default_institutional_plan_id = 5
        
        if plan_id in [default_individual_plan_id, default_institutional_plan_id]:
            flash(f'Cannot mark the default {"institutional" if plan["is_institution"] else "individual"} plan "{plan["name"]}" as inactive.', 'error')
            return redirect(url_for('admin.manage_content'))
        
        if plan['is_active']:
            cursor.execute("""
                SELECT u.id, u.username, u.email, u.subscription_plan_id, u.subscription_end
                FROM users u
                WHERE u.subscription_plan_id = %s AND u.subscription_status = 'active'
            """, (plan_id,))
            users = cursor.fetchall()
            
            cursor.execute("""
                SELECT i.id, i.name, i.email, i.subscription_plan_id, i.subscription_end
                FROM institutions i
                WHERE i.subscription_plan_id = %s
            """, (plan_id,))
            institutions = cursor.fetchall()
            
            for inst in institutions:
                if inst['subscription_end']:
                    inst['subscription_end'] = inst['subscription_end'].date()
            
            inst_count = sum(1 for inst in institutions if inst['subscription_end'] and inst['subscription_end'] >= datetime.now().date())
            
            cursor.execute("""
                UPDATE subscription_plans
                SET is_active = 0
                WHERE id = %s
            """, (plan_id,))
            
            conn.commit()
            
            message = f'Plan "{plan["name"]}" marked as inactive. '
            if len(users) > 0 or inst_count > 0:
                message += f'Existing subscriptions ({len(users)} user(s), {inst_count} institution(s)) will continue until their end date. '
            message += 'New subscriptions to this plan are now disabled.'
            flash(message, 'success')
            current_app.logger.info(f"Plan ID {plan_id} ({plan['name']}) marked as inactive by admin {current_user.username}.")
        else:
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM users
                WHERE subscription_plan_id = %s AND subscription_status = 'active'
            """, (plan_id,))
            user_count = cursor.fetchone()['count']
            
            cursor.execute("""
                SELECT id, subscription_end
                FROM institutions
                WHERE subscription_plan_id = %s
            """, (plan_id,))
            institutions = cursor.fetchall()
            
            for inst in institutions:
                if inst['subscription_end']:
                    inst['subscription_end'] = inst['subscription_end'].date()
            
            institution_count = sum(1 for inst in institutions if inst['subscription_end'] and inst['subscription_end'] >= datetime.now().date())
            
            if user_count > 0 or institution_count > 0:
                flash(f'Cannot permanently delete plan "{plan["name"]}" because it has {user_count} active user(s) and {institution_count} active institution(s).', 'error')
                return redirect(url_for('admin.manage_content'))
            
            cursor.execute("SELECT id, name FROM subscription_plans WHERE id = %s AND is_institution = 0", (default_individual_plan_id,))
            default_individual_plan = cursor.fetchone()
            if not default_individual_plan:
                flash('Default individual free plan not found.', 'error')
                return redirect(url_for('admin.manage_content'))
            
            cursor.execute("SELECT id, name FROM subscription_plans WHERE id = %s AND is_institution = 1", (default_institutional_plan_id,))
            default_institutional_plan = cursor.fetchone()
            if not default_institutional_plan:
                flash('Default institutional free plan not found.', 'error')
                return redirect(url_for('admin.manage_content'))
            
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE subscription_plan_id = %s", (plan_id,))
            inactive_user_count = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM institutions WHERE subscription_plan_id = %s", (plan_id,))
            inactive_institution_count = cursor.fetchone()['count']
            
            current_app.logger.info(f"Permanently deleting plan ID {plan_id} ({plan['name']}) by admin {current_user.username}.")
            
            if plan['is_institution']:
                cursor.execute("""
                    UPDATE institutions 
                    SET subscription_plan_id = %s, subscription_start = NULL, subscription_end = NULL, student_range = NULL
                    WHERE subscription_plan_id = %s
                """, (default_institutional_plan_id, plan_id))
                
                cursor.execute("""
                    UPDATE users 
                    SET subscription_plan_id = %s, subscription_start = NULL, subscription_end = NULL, subscription_status = 'expired'
                    WHERE subscription_plan_id = %s
                """, (default_individual_plan_id, plan_id))
            else:
                cursor.execute("""
                    UPDATE users 
                    SET subscription_plan_id = %s, subscription_start = NULL, subscription_end = NULL, subscription_status = 'expired'
                    WHERE subscription_plan_id = %s
                """, (default_individual_plan_id, plan_id))
                
                cursor.execute("""
                    UPDATE institutions 
                    SET subscription_plan_id = %s, subscription_start = NULL, subscription_end = NULL, student_range = NULL
                    WHERE subscription_plan_id = %s
                """, (default_institutional_plan_id, plan_id))
            
            cursor.execute("DELETE FROM subscription_plans WHERE id = %s", (plan_id,))
            
            conn.commit()
            
            flash(f'Plan "{plan["name"]}" permanently deleted.', 'success')
        
        return redirect(url_for('admin.manage_content'))
        
    except Exception as e:
        if conn and conn.in_transaction:
            conn.rollback()
        current_app.logger.error(f"Error in delete_plan: {str(e)}")
        flash('An error occurred while processing the plan', 'error')
        return redirect(url_for('admin.manage_content'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@admin_bp.route('/ping')
def ping():
    return 'pong', 200