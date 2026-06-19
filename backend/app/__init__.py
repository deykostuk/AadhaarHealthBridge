import os
from flask import Flask, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Instantiate database handler and migrate objects
db = SQLAlchemy()
migrate = Migrate()

def create_app(config_name="development"):
    app = Flask(__name__, static_folder='static', template_folder='templates')
    
    # Load configuration dynamically from config.py
    try:
        from config import config
        app.config.from_object(config.get(config_name, config["default"]))
    except Exception as e:
        print(f"Warning: Could not load configuration from config.py ({e}). Falling back to local SQLite.")
        app.secret_key = os.environ.get("SECRET_KEY", "startup_secret_key_validation_tracer")
        base_dir = os.path.abspath(os.path.dirname(__file__))
        app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(base_dir, 'app.db')}"
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize migrate with the app and db
    db.init_app(app)
    migrate.init_app(app, db) 
    
    with app.app_context():
        # Clean import of structural models
        from app.models.patient import (
            User, VaultProfile, VaultAccess, Document, QRScanLog, HealthMetric
        )
        
        # db.create_all() is fine for now, but once you use migrations,
        # you will rely on 'flask db upgrade' instead.
        db.create_all()
        
        from app.routes.bridge import bridge_bp
        app.register_blueprint(bridge_bp, url_prefix='/api/v1')
        
        from app.routes.health import health_bp
        app.register_blueprint(health_bp, url_prefix='/api/v1')

        @app.route('/')
        def index():
            return redirect('/api/v1/login')

        @app.route('/favicon.ico')
        def favicon():
            return app.send_static_file('icon-192.png')
        
    return app