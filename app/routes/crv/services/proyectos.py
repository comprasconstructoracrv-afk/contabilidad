"""CRV proyectos service helpers."""

from ..crv_context import (
    CRVCuentaCobrar,
    CRVCuentaPagar,
    CRVMovimiento,
    CRVTercero,
    db,
)

def _nombre_proyecto_normalizado(valor):
    return str(valor or "").strip()

def _movimientos_proyecto(empresa_id, nombre_proyecto):
    nombre = _nombre_proyecto_normalizado(nombre_proyecto)

    return (
        CRVMovimiento.query
        .filter(
            CRVMovimiento.empresa_id == empresa_id,
            db.func.lower(
                db.func.trim(
                    CRVMovimiento.proyecto
                )
            ) == nombre.lower()
        )
        .order_by(
            CRVMovimiento.fecha.asc(),
            CRVMovimiento.id.asc()
        )
        .all()
    )

def _cuentas_pagar_proyecto(empresa_id, nombre_proyecto):
    nombre = _nombre_proyecto_normalizado(nombre_proyecto)

    return (
        CRVCuentaPagar.query
        .filter(
            CRVCuentaPagar.empresa_id == empresa_id,
            db.func.lower(
                db.func.trim(
                    CRVCuentaPagar.proyecto
                )
            ) == nombre.lower()
        )
        .order_by(
            CRVCuentaPagar.fecha_documento.asc(),
            CRVCuentaPagar.id.asc()
        )
        .all()
    )

def _cuentas_cobrar_proyecto(empresa_id, nombre_proyecto):
    nombre = _nombre_proyecto_normalizado(nombre_proyecto)

    return (
        CRVCuentaCobrar.query
        .filter(
            CRVCuentaCobrar.empresa_id == empresa_id,
            db.func.lower(
                db.func.trim(
                    CRVCuentaCobrar.proyecto
                )
            ) == nombre.lower()
        )
        .order_by(
            CRVCuentaCobrar.fecha_documento.asc(),
            CRVCuentaCobrar.id.asc()
        )
        .all()
    )

def _resumen_proyecto(proyecto):
    empresa_id = proyecto.empresa_id
    movimientos = _movimientos_proyecto(
        empresa_id,
        proyecto.nombre
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
            # Conservamos el mismo criterio del dashboard:
            # un egreso no clasificado se considera gasto.
            gastos += valor

    cuentas_pagar = _cuentas_pagar_proyecto(
        empresa_id,
        proyecto.nombre
    )

    for cuenta in cuentas_pagar:
        cuenta.recalcular_saldos()

    cuentas_cobrar = _cuentas_cobrar_proyecto(
        empresa_id,
        proyecto.nombre
    )

    for cuenta in cuentas_cobrar:
        cuenta.recalcular_saldos()

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

    costos = compras + gastos
    resultado = ingresos - costos

    presupuesto = float(
        proyecto.presupuesto or 0
    )

    porcentaje_presupuesto = (
        (costos / presupuesto) * 100
        if presupuesto > 0
        else 0
    )

    disponible_presupuesto = (
        presupuesto - costos
        if presupuesto > 0
        else 0
    )

    return {
        "movimientos": movimientos,
        "cuentas_pagar": cuentas_pagar,
        "cuentas_cobrar": cuentas_cobrar,
        "ingresos": ingresos,
        "compras": compras,
        "gastos": gastos,
        "costos": costos,
        "resultado": resultado,
        "cxp_facturado": cxp_facturado,
        "cxp_pagado": cxp_pagado,
        "cxp_pendiente": cxp_pendiente,
        "cxc_facturado": cxc_facturado,
        "cxc_cobrado": cxc_cobrado,
        "cxc_pendiente": cxc_pendiente,
        "presupuesto": presupuesto,
        "porcentaje_presupuesto": porcentaje_presupuesto,
        "disponible_presupuesto": disponible_presupuesto,
        "cantidad_movimientos": len(movimientos),
    }

def _clientes_proyectos_crv(empresa_id):
    return (
        CRVTercero.query
        .filter(
            CRVTercero.empresa_id == empresa_id,
            CRVTercero.activo.is_(True),
            CRVTercero.tipo_tercero.in_(
                ["CLIENTE", "TERCERO"]
            )
        )
        .order_by(
            CRVTercero.razon_social.asc()
        )
        .all()
    )

__all__ = ['_clientes_proyectos_crv', '_cuentas_cobrar_proyecto', '_cuentas_pagar_proyecto', '_movimientos_proyecto', '_nombre_proyecto_normalizado', '_resumen_proyecto']
