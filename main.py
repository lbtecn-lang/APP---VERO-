import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import Ingredient, Recipe, RecipeIngredient, UNIDADES_POR_CATEGORIA
from currency import get_current_rate, refresh_rate

main_bp = Blueprint("main", __name__)


def _ingredientes_json(ingredientes):
    return json.dumps([
        {
            "id": i.id,
            "nombre": i.nombre,
            "categoria": i.categoria,
            "unidad_compra": i.unidad_compra,
            "costo_unitario_base": round(i.costo_unitario_base, 8),
        }
        for i in ingredientes
    ])


def _receta_items_json(receta):
    if not receta:
        return "[]"
    return json.dumps([
        {"ingredient_id": it.ingredient_id, "cantidad": it.cantidad_usada, "unidad": it.unidad_usada}
        for it in receta.items
    ])


# ---------- Tasa de cambio (API interna para el JS) ----------
@main_bp.route("/api/tasa")
@login_required
def api_tasa():
    rate = get_current_rate()
    if rate is None:
        return jsonify({"tasa": None, "fecha": None, "error": "No se pudo obtener la tasa BCV."})
    return jsonify({"tasa": rate.tasa_usd_ves, "fecha": rate.fecha,
                     "actualizado": rate.updated_at.isoformat()})


@main_bp.route("/api/tasa/actualizar", methods=["POST"])
@login_required
def api_tasa_actualizar():
    tasa = refresh_rate()
    if tasa is None:
        return jsonify({"ok": False, "error": "No se pudo consultar la fuente BCV en este momento."}), 502
    return jsonify({"ok": True, "tasa": tasa})


# ---------- Inventario ----------
@main_bp.route("/inventario")
@login_required
def inventario():
    ingredientes = Ingredient.query.filter_by(user_id=current_user.id).order_by(Ingredient.nombre).all()
    return render_template("inventory.html", ingredientes=ingredientes)


@main_bp.route("/inventario/nuevo", methods=["POST"])
@login_required
def inventario_nuevo():
    unidad = request.form.get("unidad_compra", "unidad").strip()
    ing = Ingredient(
        user_id=current_user.id,
        nombre=request.form.get("nombre", "").strip(),
        presentacion_cantidad=float(request.form.get("presentacion_cantidad") or 1),
        unidad_compra=unidad,
        presentacion_unidad=unidad,
        precio_compra_usd=float(request.form.get("precio_compra_usd") or 0),
        stock_actual=float(request.form.get("stock_actual") or 0),
        stock_minimo=float(request.form.get("stock_minimo") or 0),
    )
    db.session.add(ing)
    db.session.commit()
    flash(f"Ingrediente '{ing.nombre}' agregado.", "ok")
    return redirect(url_for("main.inventario"))


@main_bp.route("/inventario/<int:ing_id>/editar", methods=["POST"])
@login_required
def inventario_editar(ing_id):
    ing = Ingredient.query.filter_by(id=ing_id, user_id=current_user.id).first_or_404()
    ing.nombre = request.form.get("nombre", ing.nombre).strip()
    ing.presentacion_cantidad = float(request.form.get("presentacion_cantidad") or 1)
    unidad = request.form.get("unidad_compra", ing.unidad_compra).strip()
    ing.unidad_compra = unidad
    ing.presentacion_unidad = unidad
    ing.precio_compra_usd = float(request.form.get("precio_compra_usd") or 0)
    ing.stock_actual = float(request.form.get("stock_actual") or 0)
    ing.stock_minimo = float(request.form.get("stock_minimo") or 0)
    db.session.commit()
    flash(f"Ingrediente '{ing.nombre}' actualizado.", "ok")
    return redirect(url_for("main.inventario"))


@main_bp.route("/inventario/<int:ing_id>/eliminar", methods=["POST"])
@login_required
def inventario_eliminar(ing_id):
    ing = Ingredient.query.filter_by(id=ing_id, user_id=current_user.id).first_or_404()
    db.session.delete(ing)
    db.session.commit()
    flash("Ingrediente eliminado.", "ok")
    return redirect(url_for("main.inventario"))


# ---------- Calculadora / Recetas ----------
@main_bp.route("/")
@login_required
def calculadora():
    ingredientes = Ingredient.query.filter_by(user_id=current_user.id).order_by(Ingredient.nombre).all()
    recetas = Recipe.query.filter_by(user_id=current_user.id).order_by(Recipe.creado.desc()).all()
    return render_template("dashboard.html", ingredientes=ingredientes, recetas=recetas, receta=None,
                            ingredientes_json=_ingredientes_json(ingredientes),
                            receta_items_json="[]",
                            unidades_json=json.dumps(UNIDADES_POR_CATEGORIA))


@main_bp.route("/receta/<int:recipe_id>")
@login_required
def ver_receta(recipe_id):
    ingredientes = Ingredient.query.filter_by(user_id=current_user.id).order_by(Ingredient.nombre).all()
    recetas = Recipe.query.filter_by(user_id=current_user.id).order_by(Recipe.creado.desc()).all()
    receta = Recipe.query.filter_by(id=recipe_id, user_id=current_user.id).first_or_404()
    return render_template("dashboard.html", ingredientes=ingredientes, recetas=recetas, receta=receta,
                            ingredientes_json=_ingredientes_json(ingredientes),
                            receta_items_json=_receta_items_json(receta),
                            unidades_json=json.dumps(UNIDADES_POR_CATEGORIA))


@main_bp.route("/receta/guardar", methods=["POST"])
@login_required
def guardar_receta():
    recipe_id = request.form.get("recipe_id")
    if recipe_id:
        receta = Recipe.query.filter_by(id=recipe_id, user_id=current_user.id).first_or_404()
        receta.items.clear()
    else:
        receta = Recipe(user_id=current_user.id)
        db.session.add(receta)

    receta.nombre = request.form.get("nombre", "Receta sin nombre").strip()
    receta.porciones = float(request.form.get("porciones") or 1)
    receta.empaques_usd = float(request.form.get("empaques_usd") or 0)
    receta.otros_gastos_usd = float(request.form.get("otros_gastos_usd") or 0)
    receta.minutos_trabajo = float(request.form.get("minutos_trabajo") or 0)
    receta.valor_hora_usd = float(request.form.get("valor_hora_usd") or 0)
    receta.margen_pct = float(request.form.get("margen_pct") or 0)
    receta.comision_pct = float(request.form.get("comision_pct") or 0)

    ing_ids = request.form.getlist("ing_id")
    ing_cants = request.form.getlist("ing_cantidad")
    ing_unidades = request.form.getlist("ing_unidad")
    for ing_id, cantidad, unidad in zip(ing_ids, ing_cants, ing_unidades):
        if not ing_id or not cantidad:
            continue
        ingrediente = Ingredient.query.filter_by(id=int(ing_id), user_id=current_user.id).first()
        if ingrediente:
            receta.items.append(RecipeIngredient(
                ingredient=ingrediente, cantidad_usada=float(cantidad), unidad_usada=unidad or "unidad"
            ))

    db.session.commit()
    flash(f"Receta '{receta.nombre}' guardada.", "ok")
    return redirect(url_for("main.ver_receta", recipe_id=receta.id))


@main_bp.route("/receta/<int:recipe_id>/eliminar", methods=["POST"])
@login_required
def eliminar_receta(recipe_id):
    receta = Recipe.query.filter_by(id=recipe_id, user_id=current_user.id).first_or_404()
    db.session.delete(receta)
    db.session.commit()
    flash("Receta eliminada.", "ok")
    return redirect(url_for("main.calculadora"))
