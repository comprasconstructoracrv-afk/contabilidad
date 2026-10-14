from flask import Blueprint, render_template, request, redirect, session
from app.extensions import db
from app.models.sede import Sede
from app.models.movimiento import Movimiento

sedes_bp = Blueprint("sedes", __name__)


@sedes_bp.route("/sedes", methods=["GET", "POST"])
def gestionar_sedes():
    if "usuario" not in session:
        return redirect("/login")

    if "empresa_id" not in session:
        return redirect("/empresas")

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "Empresa")

    if request.method == "POST":
        nombre = request.form["nombre"].strip().upper()

        if nombre != "":
            existe = Sede.query.filter_by(nombre=nombre, empresa_id=empresa_id).first()
            if not existe:
                db.session.add(Sede(nombre=nombre, empresa_id=empresa_id))
                db.session.commit()

        return redirect("/sedes")

    sedes = Sede.query.filter_by(empresa_id=empresa_id).order_by(Sede.nombre.asc()).all()

    return render_template(
        "contabilidad/sedes.html",
        sedes=sedes,
        empresa_nombre=empresa_nombre
    )


@sedes_bp.route("/sedes/editar/<int:id>", methods=["GET", "POST"])
def editar_sede(id):
    if "usuario" not in session:
        return redirect("/login")

    if "empresa_id" not in session:
        return redirect("/empresas")

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "Empresa")

    sede = Sede.query.get_or_404(id)

    if sede.empresa_id != empresa_id:
        return redirect("/sedes")

    if request.method == "POST":
        nuevo_nombre = request.form["nombre"].strip().upper()

        if nuevo_nombre != "":
            existe = Sede.query.filter(
                Sede.id != sede.id,
                Sede.empresa_id == empresa_id,
                Sede.nombre == nuevo_nombre
            ).first()

            if not existe:
                sede.nombre = nuevo_nombre
                db.session.commit()

        return redirect("/sedes")

    return render_template(
        "contabilidad/editar_sede.html",
        sede=sede,
        empresa_nombre=empresa_nombre
    )


@sedes_bp.route("/sedes/eliminar/<int:id>", methods=["POST"])
def eliminar_sede(id):
    if "usuario" not in session:
        return redirect("/login")

    if "empresa_id" not in session:
        return redirect("/empresas")

    empresa_id = session.get("empresa_id")

    sede = Sede.query.get_or_404(id)

    if sede.empresa_id != empresa_id:
        return redirect("/sedes")

    movimientos_asociados = Movimiento.query.filter_by(sede_id=sede.id).count()

    if movimientos_asociados > 0:
        return redirect("/sedes")

    db.session.delete(sede)
    db.session.commit()

    return redirect("/sedes")