"""CRV Dashboard routes."""

from .crv_core import (
    CRVMovimiento,
    CRVTercero,
    crv_bp,
    db,
    proteger_crv,
    render_template,
    request,
    session,
)

@crv_bp.route("/")
@crv_bp.route("/dashboard")
def dashboard():

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    empresa_nombre = session.get(
        "empresa_nombre",
        "CRV CONSTRUCTORA"
    )

    mes = request.args.get(
        "mes",
        ""
    ).strip()

    query = CRVMovimiento.query.filter_by(
        empresa_id=empresa_id
    )

    if mes:

        try:

            anio_texto, mes_texto = mes.split("-")

            anio = int(anio_texto)
            numero_mes = int(mes_texto)

            query = query.filter(
                db.extract(
                    "year",
                    CRVMovimiento.fecha
                ) == anio,

                db.extract(
                    "month",
                    CRVMovimiento.fecha
                ) == numero_mes
            )

        except (ValueError, TypeError):
            pass

    movimientos = query.order_by(
        CRVMovimiento.fecha.desc(),
        CRVMovimiento.id.desc()
    ).all()

    # ========================================================
    # CÁLCULO FINANCIERO CRV
    # ========================================================

    ingresos = 0
    compras = 0

    gasto_general = 0
    gasto_nomina_afiliados = 0
    gasto_nomina_obra = 0
    gasto_anticipos = 0
    gasto_prestamos = 0
    gasto_otros = 0

    for movimiento in movimientos:

        tipo = str(
            movimiento.tipo or ""
        ).strip().upper()

        valor = float(
            movimiento.valor_neto
            or movimiento.valor
            or 0
        )

        if tipo == "INGRESO":

            ingresos += valor

        elif tipo == "COMPRA":

            compras += valor

        elif tipo == "GASTO":

            gasto_general += valor

        elif tipo in (
            "NOMINA AFILIADOS",
            "NÓMINA AFILIADOS"
        ):

            gasto_nomina_afiliados += valor

        elif tipo in (
            "NOMINA OBRA",
            "NÓMINA OBRA"
        ):

            gasto_nomina_obra += valor

        elif tipo == "ANTICIPO":

            gasto_anticipos += valor

        elif tipo in (
            "PRESTAMO EMPLEADO",
            "PRÉSTAMO EMPLEADO"
        ):

            gasto_prestamos += valor

        elif tipo in (
            "TRANSFERENCIA",
            "PAGO CUENTA POR PAGAR",
            "SALDO INICIAL CUENTA",
            "COBRO CUENTA POR COBRAR",
        ):

            # Transferencias entre cuentas propias y pagos de CxP
            # no vuelven a afectar el resultado. La compra ya se
            # reconoció cuando se registró la obligación/factura.
            pass

        else:

            gasto_otros += valor

    gastos_totales = (
        gasto_general
        + gasto_nomina_afiliados
        + gasto_nomina_obra
        + gasto_anticipos
        + gasto_prestamos
        + gasto_otros
    )

    egresos_totales = (
        compras
        + gastos_totales
    )

    utilidad = (
        ingresos
        - egresos_totales
    )

    cantidad_terceros = CRVTercero.query.filter_by(
        empresa_id=empresa_id,
        activo=True
    ).count()

    ultimos_movimientos = movimientos[:10]

    return render_template(
        "contabilidad/crv_dashboard.html",

        empresa_nombre=empresa_nombre,
        mes_actual=mes,

        ingresos=ingresos,
        compras=compras,

        gasto_general=gasto_general,
        gasto_nomina_afiliados=gasto_nomina_afiliados,
        gasto_nomina_obra=gasto_nomina_obra,
        gasto_anticipos=gasto_anticipos,
        gasto_prestamos=gasto_prestamos,
        gasto_otros=gasto_otros,

        gastos_totales=gastos_totales,
        egresos_totales=egresos_totales,
        utilidad=utilidad,

        cantidad_movimientos=len(movimientos),
        cantidad_terceros=cantidad_terceros,

        ultimos_movimientos=ultimos_movimientos
    )

__all__ = ['dashboard']
