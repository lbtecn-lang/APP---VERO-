"""
Obtiene y cachea la tasa oficial BCV (USD -> Bs).

Fuente principal: https://bcv.today/api/rate.json (API pública gratuita que
raspa la página oficial del BCV varias veces al día).
Fuente de respaldo: https://pydolarve.org/api/v1/dollar?page=bcv

La tasa se guarda en la tabla ExchangeRate. Si el último registro tiene más
de 24 horas, se intenta refrescar automáticamente al pedirla (además del job
programado que corre una vez al día).
"""
from datetime import datetime, timedelta
import requests
from extensions import db
from models import ExchangeRate

PRIMARY_URL = "https://bcv.today/api/rate.json"
FALLBACK_URL = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=bcv"
TIMEOUT = 10


def _fetch_from_source():
    """Intenta obtener la tasa desde las fuentes conocidas. Devuelve (tasa, fecha) o None."""
    try:
        r = requests.get(PRIMARY_URL, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        tasa = float(data["USD"])
        fecha = data.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
        return tasa, fecha
    except Exception:
        pass

    # Fuente de respaldo: el schema puede variar, se intentan las formas más comunes.
    try:
        r = requests.get(FALLBACK_URL, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        tasa = None
        fecha = datetime.utcnow().strftime("%Y-%m-%d")
        if isinstance(data, dict):
            if "price" in data:
                tasa = data["price"]
                fecha = data.get("last_update", fecha)
            elif "monitors" in data and isinstance(data["monitors"], dict):
                bcv = data["monitors"].get("bcv") or next(iter(data["monitors"].values()))
                tasa = bcv.get("price")
                fecha = bcv.get("last_update", fecha)
        if tasa is None:
            return None
        return float(tasa), fecha
    except Exception:
        return None


def refresh_rate(app=None):
    """Fuerza un refresco y guarda un nuevo registro si la consulta tuvo éxito."""
    result = _fetch_from_source()
    if result is None:
        return None
    tasa, fecha = result
    with (app.app_context() if app else _null_ctx()):
        existing = ExchangeRate.query.filter_by(fecha=fecha).first()
        if existing:
            existing.tasa_usd_ves = tasa
            existing.updated_at = datetime.utcnow()
        else:
            db.session.add(ExchangeRate(tasa_usd_ves=tasa, fecha=fecha))
        db.session.commit()
    return tasa


class _null_ctx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def get_current_rate():
    """Devuelve el registro más reciente, refrescando si está desactualizado (>24h) o vacío."""
    latest = ExchangeRate.query.order_by(ExchangeRate.updated_at.desc()).first()
    if latest is None or (datetime.utcnow() - latest.updated_at) > timedelta(hours=24):
        nueva_tasa = refresh_rate()
        if nueva_tasa is not None:
            latest = ExchangeRate.query.order_by(ExchangeRate.updated_at.desc()).first()
    return latest
