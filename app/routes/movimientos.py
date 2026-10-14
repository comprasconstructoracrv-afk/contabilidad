from datetime import datetime
from flask import Blueprint, render_template, request, redirect, session
from app.extensions import db
from app.models.movimiento import Movimiento
from app.models.sede import Sede

movimientos_bp = Blueprint("movimientos", __name__)


@movimientos_bp.route("/nuevo", methods=["GET", "POST"])
def nuevo_movimiento():
    if "usuario" not in session:
        return redirect("/login")

    if "empresa_id" not in session:
        return redirect("/empresas")

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "Empresa")
    sedes = Sede.query.filter_by(empresa_id=empresa_id).order_by(Sede.nombre.asc()).all()

    if request.method == "POST":
        valor_texto = request.form["valor"].strip()

        if valor_texto == "":
            return "El campo valor está vacío"

        fecha_texto = request.form["fecha"]
        fecha_convertida = datetime.strptime(fecha_texto, "%Y-%m-%d").date()

        categoria = request.form["categoria"]
        if categoria == "Otro":
            categoria = request.form.get("otra_categoria", "").strip()
            if categoria == "":
                categoria = "Otro"

        cuenta = request.form.get("cuenta", "").strip()
        if cuenta == "OTRO":
            cuenta = request.form.get("otra_cuenta", "").strip()
            if cuenta == "":
                cuenta = "OTRO"

        sede_id_texto = request.form.get("sede_id", "").strip()
        sede_id = int(sede_id_texto) if sede_id_texto.isdigit() else None

        nuevo = Movimiento(
            fecha=fecha_convertida,
            tipo=request.form["tipo"].strip().upper(),
            categoria=categoria,
            cuenta=cuenta,
            tercero=request.form.get("tercero", "").strip(),
            valor=float(valor_texto),
            descripcion=request.form["descripcion"],
            empresa_id=empresa_id,
            sede_id=sede_id
        )

        db.session.add(nuevo)
        db.session.commit()

        return redirect("/movimientos")

    return render_template(
        "contabilidad/nuevo_movimiento.html",
        empresa_nombre=empresa_nombre,
        sedes=sedes
    )


@movimientos_bp.route("/movimientos")
def ver_movimientos():
    if "usuario" not in session:
        return redirect("/login")

    if "empresa_id" not in session:
        return redirect("/empresas")

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "Empresa")
    sede_id = request.args.get("sede_id", "").strip()
    mes = request.args.get("mes", "").strip()

    query = Movimiento.query.filter_by(empresa_id=empresa_id)

    if sede_id.isdigit():
        query = query.filter_by(sede_id=int(sede_id))

    if mes:
        try:
            anio, numero_mes = mes.split("-")
            anio = int(anio)
            numero_mes = int(numero_mes)

            query = query.filter(
                db.extract("year", Movimiento.fecha) == anio,
                db.extract("month", Movimiento.fecha) == numero_mes
            )
        except ValueError:
            pass

    movimientos = query.order_by(Movimiento.fecha.desc()).all()
    sedes = Sede.query.filter_by(empresa_id=empresa_id).order_by(Sede.nombre.asc()).all()

    return render_template(
        "contabilidad/movimientos.html",
        movimientos=movimientos,
        empresa_nombre=empresa_nombre,
        sedes=sedes,
        sede_actual=sede_id,
        mes_actual=mes
    )


@movimientos_bp.route("/movimientos/editar/<int:id>", methods=["GET", "POST"])
def editar_movimiento(id):
    if "usuario" not in session:
        return redirect("/login")

    if "empresa_id" not in session:
        return redirect("/empresas")

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "Empresa")

    movimiento = Movimiento.query.get_or_404(id)

    if movimiento.empresa_id != empresa_id:
        return redirect("/movimientos")

    sedes = Sede.query.filter_by(empresa_id=empresa_id).order_by(Sede.nombre.asc()).all()

    if request.method == "POST":
        valor_texto = request.form["valor"].strip()

        if valor_texto == "":
            return "El campo valor está vacío"

        fecha_texto = request.form["fecha"]
        movimiento.fecha = datetime.strptime(fecha_texto, "%Y-%m-%d").date()

        tipo = request.form["tipo"].strip().upper()
        categoria = request.form["categoria"]

        if categoria == "Otro":
            categoria = request.form.get("otra_categoria", "").strip()
            if categoria == "":
                categoria = "Otro"

        cuenta = request.form.get("cuenta", "").strip()
        if cuenta == "OTRO":
            cuenta = request.form.get("otra_cuenta", "").strip()
            if cuenta == "":
                cuenta = "OTRO"

        sede_id_texto = request.form.get("sede_id", "").strip()
        sede_id = int(sede_id_texto) if sede_id_texto.isdigit() else None

        movimiento.tipo = tipo
        movimiento.categoria = categoria
        movimiento.cuenta = cuenta
        movimiento.tercero = request.form.get("tercero", "").strip()
        movimiento.valor = float(valor_texto)
        movimiento.descripcion = request.form["descripcion"]
        movimiento.sede_id = sede_id

        db.session.commit()
        return redirect("/movimientos")

    return render_template(
        "contabilidad/editar_movimiento.html",
        movimiento=movimiento,
        empresa_nombre=empresa_nombre,
        sedes=sedes
    )


@movimientos_bp.route("/movimientos/eliminar/<int:id>", methods=["POST"])
def eliminar_movimiento(id):
    if "usuario" not in session:
        return redirect("/login")

    if "empresa_id" not in session:
        return redirect("/empresas")

    empresa_id = session.get("empresa_id")

    movimiento = Movimiento.query.get_or_404(id)

    if movimiento.empresa_id != empresa_id:
        return redirect("/movimientos")

    db.session.delete(movimiento)
    db.session.commit()

    return redirect("/movimientos")