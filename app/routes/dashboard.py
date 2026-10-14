from flask import Blueprint, render_template, redirect, session, request
from app.models.movimiento import Movimiento
from app.models.sede import Sede
from app.models.empresa_config import EmpresaConfig
from app.extensions import db

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
def dashboard():
    if "usuario" not in session:
        return redirect("/login")

    if "empresa_id" not in session:
        return redirect("/empresas")

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "Empresa")

    config = EmpresaConfig.query.filter_by(empresa_id=empresa_id).first()
    if config and config.tipo_negocio == "HOTEL_ACCIONES":
        return redirect("/hotel-sky-view/dashboard")

    sede_id = request.args.get("sede_id", "").strip()
    mes = request.args.get("mes", "").strip()

    query = Movimiento.query.filter(Movimiento.empresa_id == empresa_id)

    if sede_id.isdigit():
        query = query.filter(Movimiento.sede_id == int(sede_id))

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

    movimientos = query.order_by(Movimiento.fecha.desc(), Movimiento.id.desc()).all()

    ingresos = 0
    gastos = 0
    ingresos_por_cuenta = {}

    for m in movimientos:
        tipo = str(m.tipo or "").strip().upper()
        valor = float(m.valor or 0)

        if tipo == "INGRESO":
            ingresos += valor
            cuenta = m.cuenta if m.cuenta else "SIN DEFINIR"
            ingresos_por_cuenta[cuenta] = ingresos_por_cuenta.get(cuenta, 0) + valor

        elif tipo == "GASTO":
            gastos += valor

    utilidad = ingresos - gastos
    sedes = Sede.query.filter_by(empresa_id=empresa_id).order_by(Sede.nombre.asc()).all()
    ingresos_cuentas_ordenadas = sorted(ingresos_por_cuenta.items(), key=lambda x: x[1], reverse=True)

    return render_template(
        "contabilidad/dashboard.html",
        ingresos=ingresos,
        gastos=gastos,
        utilidad=utilidad,
        perdida=abs(utilidad) if utilidad < 0 else 0,
        empresa_nombre=empresa_nombre,
        sedes=sedes,
        sede_actual=sede_id,
        mes_actual=mes,
        ingresos_cuentas=ingresos_cuentas_ordenadas
    )