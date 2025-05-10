from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO
from flask_login import LoginManager, current_user
from flask_mail import Mail
from apscheduler.schedulers.background import BackgroundScheduler
from utils.db import get_db_connection
import logging
from logging.handlers import RotatingFileHandler
from config import Config
import socket
import atexit
from models import User
from werkzeug.exceptions import TooManyRequests
import importlib.util
from routes.admin import admin_bp, set_socketio

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
app.config['WTF_CSRF_ENABLED'] = True
app.config['SESSION_COOKIE_SECURE'] = True  # Enable in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.choose_login'

@login_manager.user_loader
def load_user(user_id):
    try:
        user = User.get_by_id(user_id)
        if user:
            app.logger.info(f"Loaded user {user_id}")
        else:
            app.logger.warning(f"User {user_id} not found")
        return user
    except Exception as e:
        app.logger.error(f"Error loading user {user_id}: {str(e)}")
        return None

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('app.log', maxBytes=10*1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
handler.setFormatter(formatter)
logger.addHandler(handler)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

# Determine SocketIO async mode
def get_async_mode():
    if importlib.util.find_spec('eventlet'):
        try:
            import eventlet
            app.logger.info("Eventlet detected; using async_mode='eventlet'")
            return 'eventlet'
        except ImportError:
            app.logger.warning("Eventlet import failed; falling back to threading. Install with 'pip install eventlet'.")
            return 'threading'
    else:
        app.logger.warning("Eventlet not installed; falling back to threading. Install with 'pip install eventlet'.")
        return 'threading'

# Initialize SocketIO with fallback
async_mode = get_async_mode()
try:
    socketio = SocketIO(
        app,
        async_mode=async_mode,
        cors_allowed_origins=['http://localhost:5000', 'http://127.0.0.1:5000'],
    )
    app.logger.info(f"SocketIO initialized with async_mode='{async_mode}'")
except ValueError as e:
    app.logger.error(f"SocketIO initialization failed with async_mode='{async_mode}': {str(e)}")
    app.logger.info("Retrying SocketIO initialization with async_mode='threading'")
    socketio = SocketIO(
        app,
        async_mode='threading',
        cors_allowed_origins=['http://localhost:5000'],
        logger=True,
        engineio_logger=True
    )
    app.logger.info("SocketIO initialized with async_mode='threading'")

app.extensions['socketio'] = socketio  # Store for blueprints

# Initialize other extensions
csrf = CSRFProtect(app)
mail = Mail(app)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["6000 per day", "100 per hour"],
    storage_uri=app.config.get('REDIS_URL', "memory://"),
    storage_options={"socket_connect_timeout": 5},
    enabled=not app.debug
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

try:
    scheduler.add_job(reassign_expired_subscriptions, 'interval', days=1)
    scheduler.start()
    app.logger.info("APScheduler started")
except Exception as e:
    app.logger.error(f"Failed to start APScheduler: {str(e)}")

# Shutdown scheduler on app exit
atexit.register(lambda: scheduler.shutdown() if scheduler.running else None)

# Import routes after app is created
try:
    from routes.auth import create_auth_bp
    from routes.admin import admin_bp
    from routes.user import user_bp
    from routes.quiz import quiz_bp
    from routes.institution import institution_bp
    app.logger.info("Blueprints imported successfully")
except Exception as e:
    app.logger.error(f"Failed to import blueprints: {str(e)}", exc_info=True)
    raise

# Create auth blueprint with limiter
auth_bp = create_auth_bp(limiter)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
try:
    set_socketio(socketio, app)# Pass socketio to admin blueprint
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.logger.info("Admin blueprint registered with socketio")
except AttributeError:
    app.logger.error("Admin blueprint does not have set_socketio method. Update routes/admin.py.")
    raise
app.register_blueprint(user_bp, url_prefix='/user')
app.register_blueprint(quiz_bp, url_prefix='/quiz')
app.register_blueprint(institution_bp, url_prefix='/institution')

# Root route
@app.route('/')
def index():
    if not current_user.is_authenticated:
        app.logger.info("Unauthenticated user redirected to login")
        return redirect(url_for('auth.choose_login'))
    
    # Redirect based on role
    if current_user.role == 'superadmin':
        app.logger.info(f"Superadmin {current_user.id} redirected to admin dashboard")
        return redirect(url_for('admin.admin_dashboard'))
    elif current_user.role == 'instituteadmin':
        app.logger.info(f"Institute admin {current_user.id} redirected to institution dashboard")
        return redirect(url_for('institution.institution_dashboard'))
    else:
        app.logger.info(f"User {current_user.id} redirected to user dashboard")
        return redirect(url_for('user.user_dashboard'))

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    app.logger.error(f"404 error: {str(error)}", exc_info=True)
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f"500 error: {str(error)}", exc_info=True)
    return render_template('errors/500.html'), 500

@app.errorhandler(CSRFError)
def csrf_error(error):
    app.logger.error(f"CSRF error: {str(error)}")
    flash('Session expired. Please try again.', 'danger')
    if current_user.is_authenticated:
        if current_user.role == 'superadmin':
            return redirect(url_for('admin.admin_dashboard'))
        elif current_user.role == 'instituteadmin':
            return redirect(url_for('institution.institution_dashboard'))
        else:
            return redirect(url_for('user.user_dashboard'))
    return redirect(url_for('auth.choose_login'))

@app.errorhandler(TooManyRequests)
def rate_limit_error(error):
    app.logger.warning(f"Rate limit exceeded: {str(error)}")
    flash('Too many requests. Please try again later.', 'danger')
    return render_template('errors/429.html'), 429

# Socket.IO error handler
@socketio.on_error_default
def handle_socketio_error(e):
    app.logger.error(f"Socket.IO error: {str(e)}", exc_info=True)

# Context processor for common variables
@app.context_processor
def inject_globals():
    return {
        'current_user': current_user,
        'degree': request.args.get('degree', '')
    }

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
    try:
        port = find_free_port()
        if port:
            app.logger.info(f"Starting server on port {port}")
            socketio.run(app, debug=True, port=port)
        else:
            app.logger.error("No free ports found between 5000 and 5100")
            print("No free ports found between 5000 and 5100")
            exit(1)
    except Exception as e:
        app.logger.error(f"Failed to start server: {str(e)}", exc_info=True)
        raise

# Note: Install eventlet for better SocketIO performance: pip install eventlet
# Ensure compatible versions: pip install --upgrade flask-socketio python-socketio python-engineio eventlet