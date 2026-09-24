from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

# Unidades controladas: (categoría, factor de conversión a la unidad base de esa categoría)
# Base de "peso" = gramo. Base de "volumen" = mililitro. "conteo" no se convierte.
UNIT_DEFS = {
    "g": ("peso", 1),
    "kg": ("peso", 1000),
    "ml": ("volumen", 1),
    "L": ("volumen", 1000),
    "unidad": ("conteo", 1),
}
UNIDADES_POR_CATEGORIA = {
    "peso": ["g", "kg"],
    "volumen": ["ml", "L"],
    "conteo": ["unidad"],
}


def categoria_de(unidad):
    return UNIT_DEFS.get(unidad, ("conteo", 1))[0]


def a_unidad_base(cantidad, unidad):
    _, factor = UNIT_DEFS.get(unidad, ("conteo", 1))
    return (cantidad or 0) * factor


class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Ingredient(db.Model):
    __tablename__ = "ingredient"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    presentacion_cantidad = db.Column(db.Float, nullable=False, default=1)
    # Columna antigua (texto libre) — se conserva por compatibilidad pero ya no se usa
    # para calcular. La unidad real y controlada es unidad_compra.
    presentacion_unidad = db.Column(db.String(40), nullable=False, default="unidad")
    unidad_compra = db.Column(db.String(10), nullable=False, default="unidad")
    precio_compra_usd = db.Column(db.Float, nullable=False, default=0)
    stock_actual = db.Column(db.Float, nullable=False, default=0)
    stock_minimo = db.Column(db.Float, nullable=False, default=0)

    @property
    def categoria(self):
        return categoria_de(self.unidad_compra)

    @property
    def costo_unitario_base(self):
        """Costo por gramo, por mililitro o por unidad, según la categoría."""
        cantidad_base = a_unidad_base(self.presentacion_cantidad, self.unidad_compra)
        if cantidad_base > 0:
            return self.precio_compra_usd / cantidad_base
        return 0

    @property
    def stock_bajo(self):
        return self.stock_actual <= self.stock_minimo


class Recipe(db.Model):
    __tablename__ = "recipe"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    porciones = db.Column(db.Float, nullable=False, default=1)
    empaques_usd = db.Column(db.Float, nullable=False, default=0)
    otros_gastos_usd = db.Column(db.Float, nullable=False, default=0)
    minutos_trabajo = db.Column(db.Float, nullable=False, default=0)
    valor_hora_usd = db.Column(db.Float, nullable=False, default=0)
    margen_pct = db.Column(db.Float, nullable=False, default=30)
    comision_pct = db.Column(db.Float, nullable=False, default=0)
    creado = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship(
        "RecipeIngredient", backref="recipe", cascade="all, delete-orphan"
    )

    def costo_ingredientes_usd(self):
        return sum(i.costo_extendido_usd for i in self.items)

    def costo_total_usd(self):
        trabajo = (self.minutos_trabajo / 60.0) * self.valor_hora_usd
        return self.costo_ingredientes_usd() + self.empaques_usd + self.otros_gastos_usd + trabajo

    def costo_por_porcion_usd(self):
        porciones = self.porciones or 1
        return self.costo_total_usd() / porciones

    def precio_sugerido_usd(self):
        margen = min(0.95, max(0, self.margen_pct / 100.0))
        comision = min(0.90, max(0, self.comision_pct / 100.0))
        denom = 1 - margen - comision
        if denom <= 0:
            return None
        return self.costo_por_porcion_usd() / denom

    def ganancia_por_porcion_usd(self):
        precio = self.precio_sugerido_usd()
        if precio is None:
            return None
        comision_monto = precio * min(0.90, max(0, self.comision_pct / 100.0))
        return precio - self.costo_por_porcion_usd() - comision_monto


class RecipeIngredient(db.Model):
    __tablename__ = "recipe_ingredient"
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey("recipe.id"), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey("ingredient.id"), nullable=False)
    cantidad_usada = db.Column(db.Float, nullable=False, default=0)
    unidad_usada = db.Column(db.String(10), nullable=False, default="unidad")

    ingredient = db.relationship("Ingredient")

    @property
    def costo_extendido_usd(self):
        if not self.ingredient:
            return 0
        cantidad_base = a_unidad_base(self.cantidad_usada, self.unidad_usada)
        return self.ingredient.costo_unitario_base * cantidad_base


class ExchangeRate(db.Model):
    __tablename__ = "exchange_rate"
    id = db.Column(db.Integer, primary_key=True)
    tasa_usd_ves = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.String(20), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
