from flask import Blueprint, render_template, redirect, url_for, flash, session, request, Response, jsonify
from flask_login import current_user, login_required
from utils.db import get_db_connection
from forms import SubscriptionForm
from datetime import datetime, timedelta
import logging
import csv
from io import StringIO
from mysql.connector import Error

user_bp = Blueprint('user', __name__, template_folder='templates/user')  # Specify template folder
logger = logging.getLogger(__name__)

@user_bp.route('/dashboard')
@login_required
def user_dashboard():
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('index'))
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Get user's subscription status with proper date handling
        cursor.execute('''
            SELECT sp.name as plan_name, sp.degree_access, 
                   DATE(u.subscription_start) as subscription_start, 
                   DATE(u.subscription_end) as subscription_end, 
                   u.subscription_status,
                   CASE 
                       WHEN u.subscription_end < CURDATE() THEN 'expired'
                       WHEN u.subscription_status = 'active' AND u.subscription_end >= CURDATE() THEN 'active'
                       ELSE u.subscription_status
                   END as current_status
            FROM users u
            LEFT JOIN subscription_plans sp ON u.subscription_plan_id = sp.id
            WHERE u.id = %s
        ''', (current_user.id,))
        subscription = cursor.fetchone()
        
        # Get available subjects based on subscription
        if subscription and subscription['current_status'] == 'active':
            if subscription['degree_access'] == 'both':
                cursor.execute('''
                    SELECT s.id, s.name, s.degree_type
                    FROM subjects s
                    ORDER BY s.name
                ''')
            else:
                cursor.execute('''
                    SELECT s.id, s.name, s.degree_type
                    FROM subjects s
                    WHERE s.degree_type = %s
                    ORDER BY s.name
                ''', (subscription['degree_access'],))
        else:
            cursor.execute('''
                SELECT s.id, s.name, s.degree_type
                FROM subjects s
                WHERE s.degree_type = 'Dpharm'  -- Assuming 'Dpharm' as default free access
                ORDER BY s.name
            ''')
        subjects = cursor.fetchall()
        
        # Get recent activity
        cursor.execute('''
            SELECT q.id, q.question, q.chapter, q.difficulty, 
                   s.name as subject_name, q.created_at
            FROM questions q
            JOIN subjects s ON q.subject_id = s.id
            WHERE q.created_by = %s
            ORDER BY q.created_at DESC
            LIMIT 5
        ''', (current_user.id,))
        recent_activity = cursor.fetchall()
        
        # Get recent quiz results for statistics
        cursor.execute('''
            SELECT r.id, r.score, r.total_questions, r.time_taken, r.date_taken
            FROM results r
            WHERE r.user_id = %s
            ORDER BY r.date_taken DESC
            LIMIT 5
        ''', (current_user.id,))
        results = cursor.fetchall()
        
        return render_template('user/user_dashboard.html',
                             user_subscription=subscription,
                             subjects=subjects,
                             recent_activity=recent_activity,
                             results=results,
                             role=current_user.role,
                             now=datetime.now().date())
    except Error as err:
        logger.error(f"Database error in user_dashboard: {str(err)}")
        flash('Error loading dashboard.', 'danger')
        return redirect(url_for('index'))
    finally:
        cursor.close()
        conn.close()

@user_bp.route('/export_dashboard/<format>')
@login_required
def export_user_dashboard(format):
    if format not in ['csv', 'pdf']:
        flash('Unsupported export format.', 'danger')
        return redirect(url_for('user.user_dashboard'))
        
    if format == 'pdf':
        flash('PDF export functionality is coming soon.', 'info')
        return redirect(url_for('user.user_dashboard'))
        
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('user.user_dashboard'))
        
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute('''
            SELECT r.id, r.score, r.total_questions, r.time_taken, r.date_taken, s.name as subject_name
            FROM results r
            LEFT JOIN subjects s ON r.subject_id = s.id
            WHERE r.user_id = %s
            ORDER BY r.date_taken DESC
        ''', (current_user.id,))
        results = cursor.fetchall()
        
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Result ID', 'Subject', 'Score', 'Total Questions', 'Percentage', 'Time Taken (seconds)', 'Date Taken'])
        
        for result in results:
            percentage = round((result['score'] / result['total_questions']) * 100, 1) if result['total_questions'] > 0 else 0
            writer.writerow([
                result['id'], 
                result['subject_name'] or 'Unknown', 
                result['score'], 
                result['total_questions'], 
                f"{percentage}%",
                result['time_taken'], 
                result['date_taken'].strftime("%Y-%m-%d %H:%M:%S")
            ])
            
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=user_results_{current_user.username}_{datetime.now().strftime("%Y%m%d")}.csv'}
        )
    except Error as err:
        logger.error(f"Database error during export: {str(err)}")
        flash('Error exporting data.', 'danger')
        return redirect(url_for('user.user_dashboard'))
    finally:
        cursor.close()
        conn.close()

@user_bp.route('/subscriptions')
@login_required
def subscriptions():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get all subscription plans with complete details
        cursor.execute('''
            SELECT id, name, price, duration_months, description, 
                   degree_access, includes_previous_years, 
                   is_institution, student_range, custom_student_range
            FROM subscription_plans
            WHERE is_institution = FALSE
            ORDER BY price ASC
        ''')
        plans = cursor.fetchall()
        
        # Get user's current subscription if any
        cursor.execute('''
            SELECT sp.*, DATE(u.subscription_start) as subscription_start, 
                   DATE(u.subscription_end) as subscription_end, 
                   u.subscription_status
            FROM users u
            LEFT JOIN subscription_plans sp ON u.subscription_plan_id = sp.id
            WHERE u.id = %s
        ''', (current_user.id,))
        current_subscription = cursor.fetchone()

        return render_template('user/subscriptions.html',
                             plans=plans,
                             current_subscription=current_subscription)
    except Exception as e:
        logger.error(f"Error loading subscription plans: {str(e)}")
        flash('Error loading subscription plans.', 'error')
        return redirect(url_for('user.user_dashboard'))
    finally:
        if 'conn' in locals():
            conn.close()

@user_bp.route('/subscribe/<int:plan_id>', methods=['GET', 'POST'])
@login_required
def subscribe(plan_id):
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        if conn is None:
            flash('Database connection error.', 'danger')
            return redirect(url_for('user.subscriptions'))
        
        conn.autocommit = False
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('SELECT * FROM subscription_plans WHERE id = %s AND is_institution = FALSE', 
                      (plan_id,))
        plan = cursor.fetchone()
        
        if not plan:
            flash('Invalid subscription plan.', 'danger')
            return redirect(url_for('user.subscriptions'))
            
        form = SubscriptionForm()
        form.plan_id.choices = [(plan['id'], plan['name'])]
        
        if form.validate_on_submit():
            start_date = datetime.now().date()
            end_date = start_date + timedelta(days=plan['duration_months'] * 30)  # Assuming 30 days per month
            
            cursor.execute('''
                UPDATE users 
                SET subscription_plan_id = %s,
                    subscription_start = %s,
                    subscription_end = %s,
                    subscription_status = %s,
                    last_active = %s
                WHERE id = %s
            ''', (plan_id, start_date, end_date, 'active', datetime.now(), current_user.id))
            
            cursor.execute('''
                INSERT INTO subscription_history 
                (user_id, subscription_plan_id, start_date, end_date, amount_paid, payment_method) 
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (current_user.id, plan_id, start_date, end_date, plan['price'], form.payment_method.data))
            
            conn.commit()
            flash(f'You have successfully subscribed to {plan["name"]}!', 'success')
            return redirect(url_for('user.subscriptions'))
        
        return render_template('user/subscribe.html', form=form, plan=plan)
    
    except Error as err:
        if conn:
            try:
                conn.rollback()
            except Error as rollback_err:
                logger.error(f"Rollback failed: {str(rollback_err)}")
        
        logger.error(f"Database error during subscription: {str(err)}")
        flash('Error processing subscription. Please try again.', 'danger')
        return redirect(url_for('user.subscriptions'))
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            try:
                conn.close()
            except Error as close_err:
                logger.error(f"Connection close failed: {str(close_err)}")

@user_bp.route('/subscription_history')
@login_required
def subscription_history():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get user's current active subscription
        cursor.execute('''
            SELECT u.subscription_plan_id, u.subscription_start, u.subscription_end,
                   p.name as plan_name
            FROM users u
            JOIN subscription_plans p ON u.subscription_plan_id = p.id
            WHERE u.id = %s AND u.subscription_status = 'active'
        ''', (current_user.id,))
        active_subscription = cursor.fetchone()
        
        # Get subscription history
        cursor.execute('''
            SELECT sh.id, sh.start_date, sh.end_date, sh.amount_paid, sh.payment_method,
                   p.name as plan_name, p.description
            FROM subscription_history sh
            JOIN subscription_plans p ON sh.subscription_plan_id = p.id
            WHERE sh.user_id = %s
            ORDER BY sh.start_date DESC
        ''', (current_user.id,))
        history = cursor.fetchall()
        
        # Mark active subscription in history
        if active_subscription:
            for entry in history:
                # Compare both plan and dates to determine if this is the active subscription
                entry['is_active'] = (
                    entry['plan_name'] == active_subscription['plan_name'] and
                    entry['start_date'] == active_subscription['subscription_start'].date() and
                    entry['end_date'] == active_subscription['subscription_end'].date()
                )
        else:
            for entry in history:
                entry['is_active'] = False
        
        return render_template('user/subscription_history.html', 
                             history=history, 
                             now=datetime.now().date())
    except Error as err:
        logger.error(f"Database error in subscription history: {str(err)}")
        flash('Error retrieving subscription history.', 'danger')
        return redirect(url_for('user.user_dashboard'))
    finally:
        cursor.close()
        conn.close()

@user_bp.route('/activate-subscription/<int:subscription_id>', methods=['POST'])
@login_required
def activate_subscription(subscription_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # First, verify the subscription exists and belongs to the user
        cursor.execute('''
            SELECT sh.*, p.name as plan_name
            FROM subscription_history sh
            JOIN subscription_plans p ON sh.subscription_plan_id = p.id
            WHERE sh.id = %s AND sh.user_id = %s
        ''', (subscription_id, current_user.id))
        subscription = cursor.fetchone()
        
        if not subscription:
            return jsonify({'success': False, 'message': 'Subscription not found'}), 404
            
        # Check if subscription is expired
        if subscription['end_date'] < datetime.now().date():
            return jsonify({'success': False, 'message': 'Cannot activate expired subscription'}), 400
            
        # Ensure we're not in a transaction
        if conn.in_transaction:
            conn.rollback()
            
        # Begin transaction
        conn.start_transaction()
        
        # Deactivate all other subscriptions
        cursor.execute('''
            UPDATE users 
            SET subscription_status = 'expired'
            WHERE id = %s
        ''', (current_user.id,))
        
        # Activate the selected subscription
        cursor.execute('''
            UPDATE users 
            SET subscription_plan_id = %s,
                subscription_start = %s,
                subscription_end = %s,
                subscription_status = 'active'
            WHERE id = %s
        ''', (subscription['subscription_plan_id'], 
              subscription['start_date'],
              subscription['end_date'],
              current_user.id))
        
        # Commit transaction
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Successfully activated {subscription["plan_name"]} subscription'
        })
        
    except Error as err:
        if conn.in_transaction:
            conn.rollback()
        logger.error(f"Database error in activate_subscription: {str(err)}")
        return jsonify({'success': False, 'message': 'Error activating subscription'}), 500
    finally:
        cursor.close()
        conn.close()