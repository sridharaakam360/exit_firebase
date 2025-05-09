from flask import Blueprint, render_template, redirect, url_for, flash, session, request, Response, jsonify
from flask_login import current_user, login_required
from utils.db import get_db_connection
from forms import SubscriptionForm
from datetime import datetime, timedelta
import logging
import csv
from io import StringIO
from mysql.connector import Error
import traceback

user_bp = Blueprint('user', __name__, template_folder='templates/user')
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
            SELECT sp.name as plan_name, sp.degree_access, sp.is_active,
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
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('index'))
    
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Fetch active plans for display
        cursor.execute("""
            SELECT id, name, price, duration_months, degree_access, description
            FROM subscription_plans
            WHERE is_active = 1 AND is_institution = 0
            ORDER BY name
        """)
        plans = cursor.fetchall()
        
        return render_template('user/subscriptions.html', plans=plans)
        
    except Exception as e:
        logger.error(f"Error in subscriptions: {str(e)}\n{traceback.format_exc()}")
        flash('An error occurred while loading subscriptions', 'error')
        return redirect(url_for('index'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@user_bp.route('/subscribe/<int:plan_id>', methods=['GET', 'POST'])
@login_required
def subscribe(plan_id):
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('user.subscriptions'))
    
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Fetch plan details and verify it's active and not institutional
        cursor.execute("""
            SELECT id, name, price, duration_months, degree_access, description
            FROM subscription_plans
            WHERE id = %s AND is_active = 1 AND is_institution = 0
        """, (plan_id,))
        plan = cursor.fetchone()
        
        if not plan:
            flash('The selected plan is not available or has been deactivated.', 'error')
            return redirect(url_for('user.subscriptions'))
        
        form = SubscriptionForm()
        
        if form.validate_on_submit():
            # Ensure no existing transaction is active
            if conn.in_transaction:
                logger.warning(f"Existing transaction detected for user {current_user.id}, plan {plan_id}. Committing.")
                conn.commit()
            
            # Start transaction
            conn.start_transaction()
            
            # Process subscription (mock payment for demo)
            subscription_start = datetime.now()
            subscription_end = subscription_start + timedelta(days=30 * plan['duration_months'])
            
            cursor.execute("""
                UPDATE users
                SET subscription_plan_id = %s,
                    subscription_status = 'active',
                    subscription_start = %s,
                    subscription_end = %s
                WHERE id = %s
            """, (plan['id'], subscription_start, subscription_end, current_user.id))
            
            # Log subscription in history
            cursor.execute("""
                INSERT INTO subscription_history (user_id, subscription_plan_id, start_date, end_date, amount_paid, payment_method)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (current_user.id, plan['id'], subscription_start, subscription_end, plan['price'], 'mock'))
            
            conn.commit()
            flash(f'Successfully subscribed to {plan["name"]}!', 'success')
            logger.info(f"User {current_user.id} ({current_user.username}) subscribed to plan ID {plan['id']} ({plan['name']})")
            return redirect(url_for('user.user_dashboard'))
        
        return render_template('user/subscribe.html', plan=plan, form=form)
        
    except Exception as e:
        if conn.in_transaction:
            conn.rollback()
        logger.error(f"Error in subscribe for user {current_user.id}, plan {plan_id}: {str(e)}\n{traceback.format_exc()}")
        flash('An error occurred while processing your subscription', 'error')
        return redirect(url_for('user.subscriptions'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

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
        # Verify the subscription exists, belongs to the user, and plan is active
        cursor.execute('''
            SELECT sh.*, p.name as plan_name, p.is_active
            FROM subscription_history sh
            JOIN subscription_plans p ON sh.subscription_plan_id = p.id
            WHERE sh.id = %s AND sh.user_id = %s
        ''', (subscription_id, current_user.id))
        subscription = cursor.fetchone()
        
        if not subscription:
            return jsonify({'success': False, 'message': 'Subscription not found'}), 404
            
        if not subscription['is_active']:
            return jsonify({'success': False, 'message': 'Cannot activate a subscription for an inactive plan'}), 400
            
        # Check if subscription is expired
        if subscription['end_date'] < datetime.now().date():
            return jsonify({'success': False, 'message': 'Cannot activate expired subscription'}), 400
            
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
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Successfully activated {subscription["plan_name"]} subscription'
        })
        
    except Error as err:
        conn.rollback()
        logger.error(f"Database error in activate_subscription: {str(err)}")
        return jsonify({'success': False, 'message': 'Error activating subscription'}), 500
    finally:
        cursor.close()
        conn.close()