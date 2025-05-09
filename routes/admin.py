from flask import Blueprint, render_template, redirect, url_for, flash, session, request, jsonify, send_file, current_app
from utils.db import get_db_connection
from utils.security import super_admin_required
from forms import QuestionForm, UserForm
from datetime import datetime
import json
import logging
from mysql.connector import Error
from werkzeug.security import generate_password_hash
import pandas as pd
import io
import csv
from werkzeug.utils import secure_filename
import os
from functools import wraps
from flask_login import login_required, current_user
from utils.notifications import notify_subscribers_of_plan_status

admin_bp = Blueprint('admin', __name__)
logger = logging.getLogger(__name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@login_required
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('index'))
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Get user counts by role
        cursor.execute('''
            SELECT role, COUNT(*) as count 
            FROM users 
            WHERE role != 'superadmin'
            GROUP BY role
        ''')
        user_counts = cursor.fetchall()
        
        # Get content counts
        cursor.execute('SELECT COUNT(*) as count FROM subjects')
        subjects_count = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as count FROM questions')
        questions_count = cursor.fetchone()['count']
        
        return render_template('admin/dashboard.html',
                             user_counts=user_counts,
                             subjects_count=subjects_count,
                             questions_count=questions_count)
    except Error as err:
        logger.error(f"Error in admin_dashboard: {str(err)}")
        flash('Error loading dashboard.', 'danger')
        return redirect(url_for('index'))
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/manage_questions', methods=['GET', 'POST'])
@super_admin_required
def manage_questions():
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
    
    cursor = conn.cursor(dictionary=True)
    try:
        form = QuestionForm()
        
        # Get selected degree, default to empty string (All Degrees)
        selected_degree = request.form.get('degree') or request.args.get('degree', '')
        
        # If All Degrees is selected, get all subjects
        if not selected_degree:
            cursor.execute('SELECT id, name, degree_type FROM subjects ORDER BY name')
            subjects = cursor.fetchall()
        else:
            # Get subjects for specific degree
            cursor.execute('SELECT id, name, degree_type FROM subjects WHERE degree_type = %s ORDER BY name', (selected_degree,))
            subjects = cursor.fetchall()
        
        if not subjects:
            flash('No subjects available. Please add subjects first.', 'warning')
        
        # Set form dropdown choices
        form.subject_id.choices = [(s['id'], s['name']) for s in subjects]
        form.degree.data = selected_degree if selected_degree else ''

        if request.method == 'POST':
            if form.validate_on_submit():
                try:
                    topics_json = json.dumps([t.strip() for t in form.topics.data.split(',')]) if form.topics.data else '[]'
                    cursor.execute('''INSERT INTO questions 
                                    (question, option_a, option_b, option_c, option_d, correct_answer, chapter, difficulty, 
                                    subject_id, is_previous_year, previous_year, topics, explanation, created_by) 
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                                    (form.question.data, form.option_a.data, form.option_b.data,
                                     form.option_c.data, form.option_d.data, form.correct_answer.data,
                                     form.chapter.data, form.difficulty.data, form.subject_id.data,
                                     form.is_previous_year.data, 
                                     form.previous_year.data if form.is_previous_year.data else None,
                                     topics_json, form.explanation.data, session['user_id']))
                    conn.commit()
                    flash('Question added successfully.', 'success')
                    return redirect(url_for('admin.manage_questions', degree=selected_degree))
                except Error as err:
                    conn.rollback()
                    logger.error(f"Database error while adding question: {str(err)}")
                    flash('Error adding question. Please try again.', 'danger')
            else:
                # Log form errors for debugging
                for field, errors in form.errors.items():
                    for error in errors:
                        logger.error(f"Form error in {field}: {error}")
                flash('Please correct the errors in the form.', 'danger')

        # Get filter parameters
        degree_filter = request.args.get('degree', '')
        subject_filter = request.args.get('subject', '')
        difficulty_filter = request.args.get('difficulty', '')
        type_filter = request.args.get('type', '')
        search_query = request.args.get('search', '')
        page = request.args.get('page', 1, type=int)
        per_page = 20

        # Build the base query
        base_query = '''SELECT q.*, u.username, s.name AS subject_name, s.degree_type 
                       FROM questions q 
                       LEFT JOIN users u ON q.created_by = u.id 
                       JOIN subjects s ON q.subject_id = s.id 
                       WHERE 1=1'''
        query_params = []

        # Add filters
        if degree_filter:
            base_query += ' AND s.degree_type = %s'
            query_params.append(degree_filter)
            
        if subject_filter:
            base_query += ' AND q.subject_id = %s'
            query_params.append(int(subject_filter))
        
        if difficulty_filter:
            base_query += ' AND q.difficulty = %s'
            query_params.append(difficulty_filter)
        
        if type_filter == 'previous_year':
            base_query += ' AND q.is_previous_year = TRUE'
        elif type_filter == 'practice':
            base_query += ' AND q.is_previous_year = FALSE'
        
        if search_query:
            base_query += ' AND (q.question LIKE %s OR q.chapter LIKE %s OR q.topics LIKE %s)'
            search_term = f'%{search_query}%'
            query_params.extend([search_term, search_term, search_term])

        # Get total count for pagination
        count_query = f'SELECT COUNT(*) as total FROM ({base_query}) as filtered_questions'
        cursor.execute(count_query, query_params)
        total_questions = cursor.fetchone()['total']
        total_pages = (total_questions + per_page - 1) // per_page

        # Add pagination
        base_query += ' ORDER BY q.id DESC LIMIT %s OFFSET %s'
        offset = (page - 1) * per_page
        query_params.extend([per_page, offset])

        # Execute final query
        cursor.execute(base_query, query_params)
        questions = cursor.fetchall()

        return render_template('admin/manage_questions.html', 
                             questions=questions, 
                             subjects=subjects, 
                             form=form, 
                             page=page, 
                             total_pages=total_pages, 
                             total_questions=total_questions,
                             selected_degree=degree_filter)
    
    except Error as err:
        conn.rollback()
        logger.error(f"Database error in manage_questions: {str(err)}")
        flash('Error processing questions.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/edit_question/<int:question_id>', methods=['GET', 'POST'])
@super_admin_required
def edit_question(question_id):
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('admin.manage_questions'))
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute('SELECT id, name FROM subjects ORDER BY name')
        subjects = cursor.fetchall()
        form = QuestionForm()
        form.subject_id.choices = [(s['id'], s['name']) for s in subjects]

        cursor.execute('''SELECT q.*, s.name AS subject_name
                         FROM questions q JOIN subjects s ON q.subject_id = s.id 
                         WHERE q.id = %s''', (question_id,))
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
            form.topics.data = ', '.join(json.loads(question['topics'])) if question['topics'] else ''
            form.explanation.data = question['explanation']
        elif form.validate_on_submit():
            topics_json = json.dumps([t.strip() for t in form.topics.data.split(',')]) if form.topics.data else '[]'
            cursor.execute('''UPDATE questions 
                            SET question = %s, option_a = %s, option_b = %s, option_c = %s, option_d = %s, 
                            correct_answer = %s, chapter = %s, difficulty = %s, subject_id = %s, 
                            is_previous_year = %s, previous_year = %s, topics = %s, explanation = %s 
                            WHERE id = %s''',
                            (form.question.data, form.option_a.data, form.option_b.data,
                             form.option_c.data, form.option_d.data, form.correct_answer.data,
                             form.chapter.data, form.difficulty.data, form.subject_id.data,
                             form.is_previous_year.data, form.previous_year.data if form.is_previous_year.data else None,
                             topics_json, form.explanation.data, question_id))
            conn.commit()
            flash('Question updated successfully.', 'success')
            return redirect(url_for('admin.manage_questions'))

        return render_template('admin/edit_question.html', form=form, question_id=question_id)
    
    except Error as err:
        conn.rollback()
        logger.error(f"Database error in edit_question: {str(err)}")
        flash('Error updating question.', 'danger')
        return redirect(url_for('admin.manage_questions'))
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/delete_question/<int:qid>', methods=['POST'])
@super_admin_required
def delete_question(qid):
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('admin.manage_questions'))
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT id FROM questions WHERE id = %s', (qid,))
        if not cursor.fetchone():
            flash('Question not found.', 'danger')
        else:
            cursor.execute('DELETE FROM questions WHERE id = %s', (qid,))
            conn.commit()
            flash('Question deleted successfully.', 'success')
            logger.info(f"Question {qid} deleted by superadmin {session['username']}")
    except Error as err:
        conn.rollback()
        logger.error(f"Database error during question deletion: {str(err)}")
        flash('Error deleting question.', 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin.manage_questions'))

@admin_bp.route('/manage_users', methods=['GET', 'POST'])
@login_required
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
        
        # Get counts for each user type
        cursor.execute('''
            SELECT 
                role,
                COUNT(*) as count,
                MAX(last_active) as last_active
            FROM users 
            WHERE role != 'superadmin'
            GROUP BY role
        ''')
        user_counts = {row['role']: {'count': row['count'], 'last_active': row['last_active']} for row in cursor.fetchall()}
        
        # Build the WHERE clause based on user type
        if user_type == 'all':
            where_clause = 'u.role != "superadmin"'
        else:
            where_clause = f'u.role = "{user_type}"'
        
        # Get total count
        cursor.execute(f'SELECT COUNT(*) as total FROM users u WHERE {where_clause}')
        total_users = cursor.fetchone()['total']
        total_pages = (total_users + per_page - 1) // per_page
        
        # Get paginated users with institution info
        if user_type == 'instituteadmin':
            cursor.execute(f'''
                SELECT u.*, sp.name as plan_name,
                       i.name as institution_name, i.institution_code,
                       u.last_active
                FROM users u 
                LEFT JOIN subscription_plans sp ON u.subscription_plan_id = sp.id 
                JOIN institutions i ON u.id = i.admin_id
                WHERE {where_clause}
                ORDER BY u.created_at DESC
                LIMIT %s OFFSET %s
            ''', (per_page, offset))
        elif user_type == 'student':
            cursor.execute(f'''
                SELECT u.*, sp.name as plan_name,
                       i.name as institution_name, i.institution_code,
                       u.last_active
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
                SELECT u.*, sp.name as plan_name,
                       i.name as institution_name, i.institution_code,
                       u.last_active
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
        logger.error(f"Database error in manage_users: {str(err)}")
        flash('Error retrieving users.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/add_user', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('admin.manage_users'))
    
    cursor = conn.cursor(dictionary=True)
    form = UserForm()
    
    try:
        if request.method == 'POST':
            logger.info(f"Form data: {request.form}")
            logger.info(f"Form validation: {form.validate_on_submit()}")
            logger.info(f"Form errors: {form.errors}")
            
            if form.validate_on_submit():
                # Check if username or email already exists
                cursor.execute('SELECT id FROM users WHERE username = %s OR email = %s', 
                            (form.username.data, form.email.data))
                if cursor.fetchone():
                    flash('Username or email already exists.', 'danger')
                    return redirect(url_for('admin.add_user'))
                
                password_hash = generate_password_hash(form.password.data)
                
                try:
                    # Insert user
                    logger.info(f"Inserting user: {form.username.data}, {form.email.data}, {form.role.data}")
                    
                    cursor.execute('''
                        INSERT INTO users (username, email, password_hash, role, status)
                        VALUES (%s, %s, %s, %s, %s)
                    ''', (form.username.data, form.email.data, password_hash, form.role.data, form.status.data))
                    user_id = cursor.lastrowid
                    logger.info(f"User inserted with ID: {user_id}")
                    
                    # For students, link to institution
                    if form.role.data == 'student':
                        institute_code = request.form.get('institute_code')
                        if not institute_code:
                            raise ValueError('Institute code is required for student users')
                        
                        cursor.execute('SELECT id FROM institutions WHERE institution_code = %s', (institute_code,))
                        institution = cursor.fetchone()
                        if not institution:
                            raise ValueError('Invalid institute code')
                        institution_id = institution['id']
                        
                        cursor.execute('''
                            INSERT INTO institution_students (institution_id, user_id)
                            VALUES (%s, %s)
                        ''', (institution_id, user_id))
                        logger.info(f"Student linked to institution with ID: {institution_id}")
                    
                    # If role is instituteadmin, create institution
                    if form.role.data == 'instituteadmin':
                        institute_name = request.form.get('institute_name')
                        institute_code = request.form.get('institute_code_admin')
                        
                        logger.info(f"Institute data: {institute_name}, {institute_code}")
                        
                        if not institute_name or not institute_code:
                            raise ValueError('Institute name and code are required for institute admin')
                        
                        cursor.execute('SELECT id FROM institutions WHERE institution_code = %s', (institute_code,))
                        if cursor.fetchone():
                            raise ValueError('Institution code already exists')
                        
                        cursor.execute('''
                            INSERT INTO institutions (name, institution_code, admin_id, email)
                            VALUES (%s, %s, %s, %s)
                        ''', (institute_name, institute_code, user_id, form.email.data))
                        institution_id = cursor.lastrowid
                        logger.info(f"Institution created with ID: {institution_id}")
                    
                    conn.commit()
                    logger.info("Transaction committed successfully")
                    flash('User added successfully.', 'success')
                    return redirect(url_for('admin.manage_users'))
                except ValueError as e:
                    conn.rollback()
                    logger.error(f"Validation error: {str(e)}")
                    flash(str(e), 'danger')
                    return redirect(url_for('admin.add_user'))
                except Error as e:
                    conn.rollback()
                    logger.error(f"Database error: {str(e)}")
                    raise e
            else:
                logger.error(f"Form validation failed: {form.errors}")
                flash('Please correct the errors in the form.', 'danger')
        
        return render_template('admin/add_user.html', form=form)
    except Error as err:
        conn.rollback()
        logger.error(f"Database error in add_user: {str(err)}")
        flash('Error adding user.', 'danger')
        return redirect(url_for('admin.manage_users'))
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
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
            # Get user data
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
            # Update user basic info
            if form.password.data:
                password_hash = generate_password_hash(form.password.data)
                cursor.execute('''
                    UPDATE users 
                    SET username = %s, email = %s, password_hash = %s, role = %s, status = %s
                    WHERE id = %s
                ''', (form.username.data, form.email.data, password_hash, form.role.data, form.status.data, user_id))
            else:
                cursor.execute('''
                    UPDATE users 
                    SET username = %s, email = %s, role = %s, status = %s
                    WHERE id = %s
                ''', (form.username.data, form.email.data, form.role.data, form.status.data, user_id))
            
            # Handle student institution relationship
            if form.role.data == 'student':
                institute_code = request.form.get('institute_code')
                if institute_code:
                    # Get institution by code
                    cursor.execute('SELECT id FROM institutions WHERE institution_code = %s', (institute_code,))
                    institution = cursor.fetchone()
                    
                    if institution:
                        # Check if relationship already exists
                        cursor.execute('''
                            SELECT id FROM institution_students 
                            WHERE user_id = %s
                        ''', (user_id,))
                        existing = cursor.fetchone()
                        
                        if existing:
                            # Update existing relationship
                            cursor.execute('''
                                UPDATE institution_students 
                                SET institution_id = %s 
                                WHERE user_id = %s
                            ''', (institution['id'], user_id))
                        else:
                            # Create new relationship
                            cursor.execute('''
                                INSERT INTO institution_students (institution_id, user_id)
                                VALUES (%s, %s)
                            ''', (institution['id'], user_id))
                    else:
                        flash('Invalid institute code. Student will not be linked to any institution.', 'warning')
                else:
                    # Remove institution relationship if no code provided
                    cursor.execute('DELETE FROM institution_students WHERE user_id = %s', (user_id,))
            
            conn.commit()
            flash('User updated successfully.', 'success')
            return redirect(url_for('admin.manage_users'))
        
        return render_template('admin/edit_user.html', form=form, user_id=user_id, is_edit=True)
    except Error as err:
        conn.rollback()
        logger.error(f"Database error in edit_user: {str(err)}")
        flash('Error updating user.', 'danger')
        return redirect(url_for('admin.manage_users'))
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('admin.manage_users'))
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Check if user is an admin of any institution
        cursor.execute('SELECT id FROM institutions WHERE admin_id = %s', (user_id,))
        institution = cursor.fetchone()
        
        if institution:
            # User is an admin of an institution, cannot be deleted
            flash('Cannot delete user because they are an admin of an institution. Please reassign or delete the institution first.', 'danger')
            return redirect(url_for('admin.manage_users'))

        # Delete user
        cursor.execute('DELETE FROM users WHERE id = %s AND role != "superadmin"', (user_id,))
        conn.commit()
        flash('User deleted successfully.', 'success')
        return redirect(url_for('admin.manage_users'))
    except Error as err:
        conn.rollback()
        logger.error(f"Database error in delete_user: {str(err)}")
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
        return redirect(url_for('auth.login'))
    
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Fetch all subscription plans
        cursor.execute("""
            SELECT id, name, price, duration_months AS duration, degree_access,
                   is_institution, student_range, includes_previous_years,
                   description, is_active
            FROM subscription_plans
            ORDER BY is_institution, name
        """)
        plans = cursor.fetchall()
        
        # Fetch users and institutions
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
        
        # Convert subscription_end to date
        for inst in institutions:
            if inst['subscription_end']:
                inst['subscription_end'] = inst['subscription_end'].date()
        
        # Precompute subscriber counts for each plan
        for plan in plans:
            plan['user_count'] = sum(1 for user in users if user['subscription_plan_id'] == plan['id'] and user['subscription_status'] == 'active')
            plan['inst_count'] = sum(1 for inst in institutions if inst['subscription_plan_id'] == plan['id'] and inst['subscription_end'] and inst['subscription_end'] >= datetime.now().date())
        
        # Fetch all subjects
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
        logger.error(f"Error in manage_content: {str(e)}")
        flash('An error occurred while managing content', 'error')
        return redirect(url_for('auth.login'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@admin_bp.route('/add_subject', methods=['POST'])
@login_required
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
        
        # Check if subject already exists
        cursor.execute("SELECT id FROM subjects WHERE name = %s", (subject_name,))
        if cursor.fetchone():
            flash('A subject with this name already exists', 'error')
            return redirect(url_for('admin.manage_content'))
        
        # Insert new subject
        cursor.execute("""
            INSERT INTO subjects (name, degree_type, description)
            VALUES (%s, %s, %s)
        """, (subject_name, degree_type, description))
        
        conn.commit()
        flash('Subject added successfully', 'success')
        logger.info(f"Admin {session['username']} added subject: {subject_name}")
        return redirect(url_for('admin.manage_content'))
        
    except Exception as e:
        if conn and conn.in_transaction:
            conn.rollback()
        logger.error(f"Error in add_subject: {str(e)}")
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
            
            # Check if subject name already exists (excluding current subject)
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
            logger.info(f"Admin {session['username']} updated subject ID: {subject_id}, new name: {subject_name}")
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
        logger.error(f"Error in edit_subject: {str(e)}")
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
        logger.info(f"Admin {session['username']} deleted subject ID: {subject_id}")
        return redirect(url_for('admin.manage_content'))
        
    except Exception as e:
        if conn and conn.in_transaction:
            conn.rollback()
        logger.error(f"Error in delete_subject: {str(e)}")
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
        
        # Get form data
        plan_name = request.form.get('plan_name')
        price = float(request.form.get('price', 0))
        duration = int(request.form.get('duration', 0))
        degree_access = request.form.get('degree_access')
        description = request.form.get('description', '')
        includes_previous_years = 1 if request.form.get('includes_previous_years') else 0
        is_institution = 1 if request.form.get('is_institution') else 0
        student_range = int(request.form.get('student_range', 0)) if is_institution else None
        
        # Validate inputs
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
        
        # Check if plan name already exists
        cursor.execute("SELECT id FROM subscription_plans WHERE name = %s", (plan_name,))
        if cursor.fetchone():
            flash('A plan with this name already exists', 'error')
            return redirect(url_for('admin.manage_content'))
        
        # Insert new plan
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
        logger.info(f"Admin {session['username']} added new plan: {plan_name}")
        return redirect(url_for('admin.manage_content'))
        
    except Exception as e:
        if conn and conn.in_transaction:
            conn.rollback()
        logger.error(f"Error in add_plan: {str(e)}")
        flash('An error occurred while adding the plan', 'error')
        return redirect(url_for('admin.manage_content'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@admin_bp.route('/edit_plan/<int:plan_id>', methods=['GET', 'POST'])
@login_required
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
            
            # Server-side validation
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
            
            # Validate student_range if is_institution is True
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
            
            # Check if plan name already exists (excluding current plan)
            cursor.execute("""
                SELECT id FROM subscription_plans 
                WHERE name = %s AND id != %s
            """, (name, plan_id))
            existing_plan = cursor.fetchone()
            
            if existing_plan:
                flash('A plan with this name already exists', 'error')
                return redirect(url_for('admin.edit_plan', plan_id=plan_id))
            
            # Update the plan
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
            logger.info(f"Admin {session['username']} updated plan ID: {plan_id}, new name: {name}")
            return redirect(url_for('admin.manage_content'))

        # GET request - fetch plan details
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
        logger.error(f"Error in edit_plan: {str(e)}")
        flash('An error occurred while updating the plan', 'error')
        return redirect(url_for('admin.manage_content'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@admin_bp.route('/delete_plan/<int:plan_id>', methods=['POST'])
@login_required
@admin_required
def delete_plan(plan_id):
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('admin.manage_content'))
    
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Check if the plan exists and get its details
        cursor.execute("""
            SELECT id, name, is_institution, is_active
            FROM subscription_plans
            WHERE id = %s
        """, (plan_id,))
        plan = cursor.fetchone()
        
        if not plan:
            flash('Plan not found', 'error')
            return redirect(url_for('admin.manage_content'))
        
        # Define default plan IDs
        default_individual_plan_id = 1  # Free Plan for individuals
        default_institutional_plan_id = 5  # Free Institute for institutions
        
        # Prevent marking default plans as inactive
        if plan_id in [default_individual_plan_id, default_institutional_plan_id]:
            flash(f'Cannot mark the default {"institutional" if plan["is_institution"] else "individual"} plan "{plan["name"]}" as inactive.', 'error')
            return redirect(url_for('admin.manage_content'))
        
        if plan['is_active']:
            # Fetch users with active subscriptions for notification
            cursor.execute("""
                SELECT u.id, u.username, u.email, u.subscription_plan_id, u.subscription_end
                FROM users u
                WHERE u.subscription_plan_id = %s AND u.subscription_status = 'active'
            """, (plan_id,))
            users = cursor.fetchall()
            
            # Fetch institutions with active subscriptions for notification
            cursor.execute("""
                SELECT i.id, i.name, i.email, i.subscription_plan_id, i.subscription_end
                FROM institutions i
                WHERE i.subscription_plan_id = %s
            """, (plan_id,))
            institutions = cursor.fetchall()
            
            # Convert subscription_end to date
            for inst in institutions:
                if inst['subscription_end']:
                    inst['subscription_end'] = inst['subscription_end'].date()
            
            # Count active institutions
            inst_count = sum(1 for inst in institutions if inst['subscription_end'] and inst['subscription_end'] >= datetime.now().date())
            
            # Mark plan as inactive
            cursor.execute("""
                UPDATE subscription_plans
                SET is_active = 0
                WHERE id = %s
            """, (plan_id,))
            
            conn.commit()
            
            # After marking inactive, notify subscribers
            if plan['is_active']:
                notify_subscribers_of_plan_status(plan, users, institutions, "Marked Inactive")
            
            message = f'Plan "{plan["name"]}" marked as inactive. '
            if len(users) > 0 or inst_count > 0:
                message += f'Existing subscriptions ({len(users)} user(s), {inst_count} institution(s)) will continue until their end date. '
            message += 'New subscriptions to this plan are now disabled.'
            flash(message, 'success')
            logger.info(f"Plan ID {plan_id} ({plan['name']}) marked as inactive by admin {session['username']}. "
                        f"Affected: {len(users)} users, {inst_count} institutions.")
        else:
            # Check if there are any active subscriptions for an inactive plan
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
            
            # Convert subscription_end to date
            for inst in institutions:
                if inst['subscription_end']:
                    inst['subscription_end'] = inst['subscription_end'].date()
            
            institution_count = sum(1 for inst in institutions if inst['subscription_end'] and inst['subscription_end'] >= datetime.now().date())
            
            if user_count > 0 or institution_count > 0:
                flash(f'Cannot permanently delete plan "{plan["name"]}" because it has {user_count} active user(s) and {institution_count} active institution(s). Wait until all subscriptions expire.', 'error')
                return redirect(url_for('admin.manage_content'))
            
            # Verify default plans exist
            cursor.execute("SELECT id, name FROM subscription_plans WHERE id = %s AND is_institution = 0", (default_individual_plan_id,))
            default_individual_plan = cursor.fetchone()
            if not default_individual_plan:
                flash('Default individual free plan not found. Please create one first.', 'error')
                return redirect(url_for('admin.manage_content'))
            
            cursor.execute("SELECT id, name FROM subscription_plans WHERE id = %s AND is_institution = 1", (default_institutional_plan_id,))
            default_institutional_plan = cursor.fetchone()
            if not default_institutional_plan:
                flash('Default institutional free plan not found. Please create one first.', 'error')
                return redirect(url_for('admin.manage_content'))
            
            # Count inactive/expired subscriptions for logging
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE subscription_plan_id = %s", (plan_id,))
            inactive_user_count = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM institutions WHERE subscription_plan_id = %s", (plan_id,))
            inactive_institution_count = cursor.fetchone()['count']
            
            # Log the deletion action
            logger.info(f"Permanently deleting plan ID {plan_id} ({plan['name']}) by admin {session['username']}. "
                        f"Reassigning {inactive_user_count} users to plan ID {default_individual_plan_id} ({default_individual_plan['name']}) "
                        f"and {inactive_institution_count} institutions to plan ID {default_institutional_plan_id} ({default_institutional_plan['name']}).")
            
            # Reassign users and institutions
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
            
            # Delete subscription history entries
            cursor.execute("DELETE FROM subscription_history WHERE subscription_plan_id = %s", (plan_id,))
            
            # Delete the plan
            cursor.execute("DELETE FROM subscription_plans WHERE id = %s", (plan_id,))
            
            conn.commit()
            
            flash(f'Plan "{plan["name"]}" permanently deleted. {inactive_user_count} user(s) reassigned to "{default_individual_plan["name"]}" '
                  f'and {inactive_institution_count} institution(s) reassigned to "{default_institutional_plan["name"]}".', 'success')
        
        return redirect(url_for('admin.manage_content'))
        
    except Exception as e:
        if conn and conn.in_transaction:
            conn.rollback()
        logger.error(f"Error in delete_plan: {str(e)}")
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