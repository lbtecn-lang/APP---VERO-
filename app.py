import os
from flask import Flask
from sqlalchemy import inspect, text
from apscheduler.schedulers.background import BackgroundScheduler

from extensions import db, login_manager
from models import User


def migrate_schema():
    """Agrega columnas nuevas a tablas ya existentes, sin tocar ni borrar datos.
    Necesario porque el proyecto no usa Alembic/Flask-Migrate; para cambios de
    esquema más grandes en el futuro conviene migrar a eso."""
    inspector = inspect(db.engine)
    existing_tables = inspector.get_table_names()

    changes = [
        ("ingredient", "unidad_compra", "VARCHAR(10) DEFAULT 'unidad'"),
        ("recipe_ingredient", "unidad_usada", "VARCHAR(10) DEFAULT 'unidad'"),
    ]
    for table, column, coltype in changes:
        if table not in existing_tables:
            continue
        cols = [c["name"] for c in inspector.get_columns(table)]
        if column not in cols:
            db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}"))
    db.session.commit()


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "cambia-esta-clave-en-produccion")

    db_url = os.environ.get("DATABASE_URL", "sqlite:///veronik_sweet.db")
    # Render entrega postgres:// pero SQLAlchemy moderno requiere postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from auth import auth_bp, ensure_default_user
    from main import main_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()
        migrate_schema()
        ensure_default_user()

    # Job diario: refresca la tasa BCV una vez al día (además del refresco
    # automático por antigüedad que corre en cada consulta a /api/tasa).
    if not app.config.get("SCHEDULER_STARTED"):
        from currency import refresh_rate
        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(lambda: refresh_rate(app), "cron", hour=9, minute=5, id="bcv_diario")
        scheduler.start()
        app.config["SCHEDULER_STARTED"] = True

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
