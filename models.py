from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Ingredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    presentacion_cantidad = db.Column(db.Float, nullable=False, default=1)
    presentacion_unidad = db.Column(db.String(40), nullable=False, default="unidad")
    precio_compra_usd = db.Column(db.Float, nullable=False, default=0)
    stock_actual = db.Column(db.Float, nullable=False, default=0)
    stock_minimo = db.Column(db.Float, nullable=False, default=0)

    @property
    def costo_unitario_usd(self):
        if self.presentacion_cantidad and self.presentacion_cantidad > 0:
            return self.precio_compra_usd / self.presentacion_cantidad
        return 0

    @property
    def stock_bajo(self):
        return self.stock_actual <= self.stock_minimo


class Recipe(db.Model):
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
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey("recipe.id"), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey("ingredient.id"), nullable=False)
    cantidad_usada = db.Column(db.Float, nullable=False, default=0)

    ingredient = db.relationship("Ingredient")

    @property
    def costo_extendido_usd(self):
        if not self.ingredient:
            return 0
        return self.ingredient.costo_unitario_usd * self.cantidad_usada


class ExchangeRate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tasa_usd_ves = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.String(20), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
