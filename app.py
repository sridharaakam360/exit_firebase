from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO
from flask_login import LoginManager, current_user
from apscheduler.schedulers.background import BackgroundScheduler
from utils.db import get_db_connection
import logging
from config import Config
import socket
from models import User
from flask_mail import Mail

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)


app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'sridhar@shanmugha.edu.in'
app.config['MAIL_PASSWORD'] = 'hhcr fzip edti vukf'
mail = Mail(app)


# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.choose_login'

@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(user_id)

# Initialize extensions
csrf = CSRFProtect(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["6000 per day", "100 per hour"],
    storage_uri=app.config.get('REDIS_URL', "memory://"),
    storage_options={"socket_connect_timeout": 5},
    enabled=not app.debug
)

# Setup logging
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

# Initialize APScheduler
scheduler = BackgroundScheduler()

def reassign_expired_subscriptions():
    conn = get_db_connection()
    if not conn:
        app.logger.error("Failed to connect to database for reassign_expired_subscriptions")
        return
    cursor = conn.cursor()
    try:
        # Reassign users
        cursor.execute("""
            UPDATE users
            SET subscription_plan_id = %s, subscription_status = 'expired',
                subscription_start = NULL, subscription_end = NULL
            WHERE subscription_status = 'active' AND subscription_end < CURDATE()
        """, (1,))  # Default individual plan ID
        
        # Reassign institutions
        cursor.execute("""
            UPDATE institutions
            SET subscription_plan_id = %s, subscription_start = NULL,
                subscription_end = NULL, student_range = NULL
            WHERE subscription_end < CURDATE()
        """, (5,))  # Default institutional plan ID
        
        conn.commit()
        app.logger.info("Reassigned expired subscriptions to default plans")
    except Exception as e:
        app.logger.error(f"Error in reassign_expired_subscriptions: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

scheduler.add_job(reassign_expired_subscriptions, 'interval', days=1)
scheduler.start()

# Import routes after app is created
from routes.auth import create_auth_bp
from routes.admin import admin_bp
from routes.user import user_bp
from routes.quiz import quiz_bp
from routes.institution import institution_bp

# Create auth blueprint with limiter
auth_bp = create_auth_bp(limiter)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(user_bp, url_prefix='/user')
app.register_blueprint(quiz_bp, url_prefix='/quiz')
app.register_blueprint(institution_bp, url_prefix='/institution')

# Root route
@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.choose_login'))
    
    # If user is authenticated, redirect based on role
    if current_user.role == 'superadmin':
        return redirect(url_for('admin.admin_dashboard'))
    elif current_user.role == 'instituteadmin':
        return redirect(url_for('institution.institution_dashboard'))
    else:
        return redirect(url_for('user.user_dashboard'))

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html'), 500

def find_free_port(start_port=5000, max_port=5100):
    """Find a free port to bind to"""
    for port in range(start_port, max_port):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('127.0.0.1', port))
            sock.close()
            return port
        except OSError:
            continue
    return None

if __name__ == '__main__':
    port = find_free_port()
    if port:
        socketio.run(app, debug=True, port=port)
    else:
        print("No free ports found between 5000 and 5100")
        exit(1)