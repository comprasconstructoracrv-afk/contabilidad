"""CRV cierres service helpers."""

from ..crv_context import (
    CRVCierreMensual,
    CRVCobroCuentaCobrar,
    CRVCuentaCobrar,
    CRVCuentaPagar,
    CRVMovimiento,
    CRVPagoCuentaPagar,
    calendar,
    crv_bp,
    date,
    datetime,
    db,
    flash,
    redirect,
    request,
    session,
)
from .bancos import (
    _saldo_cuenta_hasta,
    _conciliacion_periodo,
)
from .reportes_data import (
    _nombre_cuenta_valido,
    _valor_movimiento_bancario,
    _movimiento_es_bancario,
)
from .validation import (
    usuario_valido,
)

def _rango_mes(anio, mes):
    ultimo_dia = calendar.monthrange(
        anio,
        mes
    )[1]

    return (
        date(anio, mes, 1),
        date(anio, mes, ultimo_dia)
    )

def _cierre_periodo(empresa_id, anio, mes):
    return (
        CRVCierreMensual.query
        .filter_by(
            empresa_id=empresa_id,
            anio=anio,
            mes=mes
        )
        .first()
    )

def _periodo_crv_cerrado(fecha, empresa_id=None):
    if not fecha:
        return False

    empresa_id = (
        empresa_id
        or session.get("empresa_id")
    )

    cierre = _cierre_periodo(
        empresa_id,
        fecha.year,
        fecha.month
    )

    return bool(
        cierre
        and cierre.estado == "CERRADO"
    )

def _movimientos_mes_crv(empresa_id, anio, mes):
    return (
        CRVMovimiento.query
        .filter(
            CRVMovimiento.empresa_id == empresa_id,
            db.extract(
                "year",
                CRVMovimiento.fecha
            ) == anio,
            db.extract(
                "month",
                CRVMovimiento.fecha
            ) == mes
        )
        .order_by(
            CRVMovimiento.fecha.asc(),
            CRVMovimiento.id.asc()
        )
        .all()
    )

def _saldo_financiero_hasta(empresa_id, fecha_fin):
    movimientos = (
        CRVMovimiento.query
        .filter(
            CRVMovimiento.empresa_id == empresa_id,
            CRVMovimiento.fecha <= fecha_fin
        )
        .order_by(
            CRVMovimiento.fecha.asc(),
            CRVMovimiento.id.asc()
        )
        .all()
    )

    cuentas = {}

    def asegurar(nombre):
        nombre = _nombre_cuenta_valido(
            nombre
        )

        if not nombre:
            return ""

        if nombre not in cuentas:
            cuentas[nombre] = 0.0

        return nombre

    for movimiento in movimientos:
        tipo = str(
            movimiento.tipo or ""
        ).strip().upper()

        origen = asegurar(
            movimiento.cuenta
        )

        destino = ""

        if tipo == "TRANSFERENCIA":
            destino = asegurar(
                movimiento.cuenta_destino
            )

        valor = _valor_movimiento_bancario(
            movimiento
        )

        if tipo == "SALDO INICIAL CUENTA":
            if origen:
                cuentas[origen] += valor
            continue

        if tipo == "INGRESO":
            if origen:
                cuentas[origen] += valor
            continue

        if tipo == "COBRO CUENTA POR COBRAR":
            if origen:
                cuentas[origen] += valor
            continue

        if tipo == "TRANSFERENCIA":
            if origen:
                cuentas[origen] -= valor
            if destino:
                cuentas[destino] += valor
            continue

        if tipo == "COMPRA":
            forma_pago = str(
                movimiento.forma_pago or ""
            ).strip().upper()

            if forma_pago in (
                "CREDITO",
                "CRÉDITO"
            ):
                continue

        if origen:
            cuentas[origen] -= valor

    return {
        "cuentas": cuentas,
        "total": sum(
            cuentas.values()
        )
    }

def _resumen_cierre_mes(
    empresa_id,
    anio,
    mes
):
    fecha_inicio, fecha_fin = _rango_mes(
        anio,
        mes
    )

    movimientos = _movimientos_mes_crv(
        empresa_id,
        anio,
        mes
    )

    ingresos = 0.0
    compras = 0.0
    gastos = 0.0

    tipos_gasto = {
        "GASTO",
        "NOMINA AFILIADOS",
        "NÓMINA AFILIADOS",
        "NOMINA OBRA",
        "NÓMINA OBRA",
        "ANTICIPO",
        "PRESTAMO EMPLEADO",
        "PRÉSTAMO EMPLEADO",
        "EGRESO",
        "OTRO EGRESO",
        "OTRO",
    }

    tipos_sin_resultado = {
        "TRANSFERENCIA",
        "PAGO CUENTA POR PAGAR",
        "COBRO CUENTA POR COBRAR",
        "SALDO INICIAL CUENTA",
    }

    for m in movimientos:
        tipo = str(
            m.tipo or ""
        ).strip().upper()

        valor = float(
            m.valor_neto
            or m.valor
            or 0
        )

        if tipo == "INGRESO":
            ingresos += valor

        elif tipo == "COMPRA":
            compras += valor

        elif tipo in tipos_gasto:
            gastos += valor

        elif tipo in tipos_sin_resultado:
            pass

        else:
            gastos += valor

    resultado = (
        ingresos
        - compras
        - gastos
    )

    cuentas_pagar = (
        CRVCuentaPagar.query
        .filter(
            CRVCuentaPagar.empresa_id == empresa_id,
            CRVCuentaPagar.fecha_documento >= fecha_inicio,
            CRVCuentaPagar.fecha_documento <= fecha_fin
        )
        .all()
    )

    for c in cuentas_pagar:
        c.recalcular_saldos()

    cuentas_cobrar = (
        CRVCuentaCobrar.query
        .filter(
            CRVCuentaCobrar.empresa_id == empresa_id,
            CRVCuentaCobrar.fecha_documento >= fecha_inicio,
            CRVCuentaCobrar.fecha_documento <= fecha_fin
        )
        .all()
    )

    for c in cuentas_cobrar:
        c.recalcular_saldos()

    cxp_facturado = sum(
        float(c.valor_neto or 0)
        for c in cuentas_pagar
    )

    cxp_pagado = sum(
        float(c.total_pagado or 0)
        for c in cuentas_pagar
    )

    cxp_pendiente = sum(
        float(c.saldo_pendiente or 0)
        for c in cuentas_pagar
    )

    cxc_facturado = sum(
        float(c.valor_neto or 0)
        for c in cuentas_cobrar
    )

    cxc_cobrado = sum(
        float(c.total_cobrado or 0)
        for c in cuentas_cobrar
    )

    cxc_pendiente = sum(
        float(c.saldo_pendiente or 0)
        for c in cuentas_cobrar
    )

    bancarios = [
        m
        for m in movimientos
        if _movimiento_es_bancario(m)
    ]

    sin_conciliar = [
        m
        for m in bancarios
        if not bool(m.revisado)
    ]

    saldos = _saldo_financiero_hasta(
        empresa_id,
        fecha_fin
    )

    # --------------------------------------------------------
    # VALIDACIÓN DE CONCILIACIÓN POR CUENTA
    # --------------------------------------------------------

    cuentas_periodo = sorted({
        _nombre_cuenta_valido(m.cuenta)
        for m in bancarios
        if _nombre_cuenta_valido(m.cuenta)
    })

    # También incluir la cuenta destino si se trata de una transferencia
    # entre cuentas propias de CRV.
    for m in bancarios:
        if str(m.tipo or "").strip().upper() == "TRANSFERENCIA":
            destino = _nombre_cuenta_valido(
                m.cuenta_destino
            )

            if destino and destino not in cuentas_periodo:
                cuentas_periodo.append(
                    destino
                )

    conciliaciones_pendientes = []

    for nombre_cuenta in cuentas_periodo:
        conciliacion_cuenta = _conciliacion_periodo(
            empresa_id,
            nombre_cuenta,
            anio,
            mes
        )

        if not conciliacion_cuenta:
            conciliaciones_pendientes.append({
                "cuenta": nombre_cuenta,
                "motivo": "SIN EXTRACTO REGISTRADO"
            })

            continue

        _, fecha_fin_periodo = _rango_mes(
            anio,
            mes
        )

        saldo_sistema_cuenta = _saldo_cuenta_hasta(
            empresa_id,
            nombre_cuenta,
            fecha_fin_periodo
        )

        diferencia_cuenta = (
            float(
                conciliacion_cuenta.saldo_extracto
                or 0
            )
            - saldo_sistema_cuenta
        )

        if (
            abs(diferencia_cuenta) >= 0.01
            or conciliacion_cuenta.estado != "CONCILIADA"
        ):
            conciliaciones_pendientes.append({
                "cuenta": nombre_cuenta,
                "motivo": (
                    f"DIFERENCIA ${diferencia_cuenta:,.0f}"
                    if abs(diferencia_cuenta) >= 0.01
                    else "CONCILIACIÓN PENDIENTE"
                )
            })

    alertas = []

    if sin_conciliar:
        alertas.append(
            (
                f"Hay {len(sin_conciliar)} movimiento(s) "
                "bancario(s) del mes pendientes de conciliación."
            )
        )

    movimientos_sin_tercero = [
        m
        for m in movimientos
        if (
            str(m.tipo or "").strip().upper()
            not in (
                "TRANSFERENCIA",
                "SALDO INICIAL CUENTA"
            )
            and not (
                m.tercero_id
                or str(
                    m.tercero_nombre
                    or ""
                ).strip()
            )
        )
    ]

    if movimientos_sin_tercero:
        alertas.append(
            (
                f"Hay {len(movimientos_sin_tercero)} movimiento(s) "
                "sin tercero identificado."
            )
        )

    if conciliaciones_pendientes:
        for item in conciliaciones_pendientes:
            alertas.append(
                (
                    f"Cuenta {item['cuenta']}: "
                    f"{item['motivo']}."
                )
            )

    return {
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "movimientos": movimientos,
        "ingresos": ingresos,
        "compras": compras,
        "gastos": gastos,
        "resultado": resultado,
        "cxp_facturado": cxp_facturado,
        "cxp_pagado": cxp_pagado,
        "cxp_pendiente": cxp_pendiente,
        "cxc_facturado": cxc_facturado,
        "cxc_cobrado": cxc_cobrado,
        "cxc_pendiente": cxc_pendiente,
        "saldo_bancos_caja": saldos["total"],
        "saldos_cuentas": saldos["cuentas"],
        "movimientos_mes": len(movimientos),
        "sin_conciliar": sin_conciliar,
        "movimientos_sin_conciliar": len(sin_conciliar),
        "alertas": alertas,
        "conciliaciones_pendientes": conciliaciones_pendientes,
        "puede_cerrar": (
            len(sin_conciliar) == 0
            and len(conciliaciones_pendientes) == 0
        ),
    }

def _fecha_formulario_cierre(valor):
    try:
        return datetime.strptime(
            str(valor or "").strip(),
            "%Y-%m-%d"
        ).date()
    except (ValueError, TypeError):
        return None

@crv_bp.before_request
def bloquear_periodos_cerrados_crv():
    if request.method != "POST":
        return None

    if not usuario_valido():
        return None

    empresa_id = session.get(
        "empresa_id"
    )

    if not empresa_id:
        return None

    endpoint = str(
        request.endpoint
        or ""
    )

    if endpoint in (
        "crv.cierre_mensual_crv",
        "crv.cierre_mensual_reabrir",
    ):
        return None

    fechas = []

    # Fecha enviada por formulario.
    for campo in (
        "fecha",
        "fecha_documento",
        "fecha_apertura",
    ):
        valor = request.form.get(
            campo
        )

        fecha = _fecha_formulario_cierre(
            valor
        )

        if fecha:
            fechas.append(
                fecha
            )

    # Movimiento existente.
    movimiento_id = (
        request.view_args.get(
            "movimiento_id"
        )
        if request.view_args
        else None
    )

    if movimiento_id:
        movimiento = db.session.get(
            CRVMovimiento,
            movimiento_id
        )

        if movimiento and movimiento.fecha:
            fechas.append(
                movimiento.fecha
            )

    # Cuenta por pagar existente.
    cuenta_id = (
        request.view_args.get(
            "cuenta_id"
        )
        if request.view_args
        else None
    )

    if cuenta_id and (
        "cuentas-por-pagar"
        in request.path
    ):
        cuenta = db.session.get(
            CRVCuentaPagar,
            cuenta_id
        )

        if (
            cuenta
            and cuenta.fecha_documento
        ):
            fechas.append(
                cuenta.fecha_documento
            )

    # Cuenta por cobrar existente.
    if cuenta_id and (
        "cuentas-por-cobrar"
        in request.path
    ):
        cuenta = db.session.get(
            CRVCuentaCobrar,
            cuenta_id
        )

        if (
            cuenta
            and cuenta.fecha_documento
        ):
            fechas.append(
                cuenta.fecha_documento
            )

    # Pago CxP existente.
    pago_id = (
        request.view_args.get(
            "pago_id"
        )
        if request.view_args
        else None
    )

    if pago_id:
        pago = db.session.get(
            CRVPagoCuentaPagar,
            pago_id
        )

        if pago and pago.fecha:
            fechas.append(
                pago.fecha
            )

    # Cobro CxC existente.
    cobro_id = (
        request.view_args.get(
            "cobro_id"
        )
        if request.view_args
        else None
    )

    if cobro_id:
        cobro = db.session.get(
            CRVCobroCuentaCobrar,
            cobro_id
        )

        if cobro and cobro.fecha:
            fechas.append(
                cobro.fecha
            )

    for fecha in fechas:
        if _periodo_crv_cerrado(
            fecha,
            empresa_id
        ):
            flash(
                (
                    f"El periodo {fecha.year}-{fecha.month:02d} "
                    "está CERRADO. Debes reabrir el mes antes "
                    "de modificar, eliminar o registrar información "
                    "con esa fecha."
                ),
                "warning"
            )

            return redirect(
                request.referrer
                or "/crv/cierre-mensual"
            )

    return None

__all__ = ['_cierre_periodo', '_fecha_formulario_cierre', '_movimientos_mes_crv', '_periodo_crv_cerrado', '_rango_mes', '_resumen_cierre_mes', '_saldo_financiero_hasta', 'bloquear_periodos_cerrados_crv']
