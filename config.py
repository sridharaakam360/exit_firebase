from datetime import datetime, timedelta

class Config:
    # Security settings
    SECRET_KEY = 'my-static-secret-key-12345'  # WARNING: Replace with a random, secure key in production
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload size
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True

    # Redis for Flask-Limiter
    REDIS_URL = 'redis://localhost:6379/0'

    # MySQL database settings
    MYSQL_HOST = 'localhost'
    MYSQL_USER = 'root'
    MYSQL_PASSWORD = 'newpass123'  # WARNING: Use environment variables in production
    MYSQL_DB = 'pharmacy_app'

    # Flask-Mail settings for email notifications
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'sridhar@shanmugha.edu.in'  # Replace with your email
    MAIL_PASSWORD = 'hhcr fzip edti vukf'  # Replace with your email app password
    MAIL_DEFAULT_SENDER = 'sridhar@shanmugha.edu.in'  # Default sender for emails