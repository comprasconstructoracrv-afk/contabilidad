"""CRV reportes data service helpers."""

from ..crv_context import (
    CRVCuentaPagar,
    CRVMovimiento,
    CRVTercero,
    db,
    request,
)
from .validation import (
    convertir_fecha,
    resumen_iva_movimientos,
)

def _reporte_filtros():
    return {
        "fecha_desde": request.args.get("fecha_desde", "").strip(),
        "fecha_hasta": request.args.get("fecha_hasta", "").strip(),
        "mes": request.args.get("mes", "").strip(),
        "anio": request.args.get("anio", "").strip(),
        "tipo": request.args.get("tipo", "").strip().upper(),
        "tercero": request.args.get("tercero", "").strip(),
        "proyecto": request.args.get("proyecto", "").strip(),
        "centro_costo": request.args.get("centro_costo", "").strip(),
    }

def _aplicar_filtros_movimientos(query, filtros):
    fecha_desde = convertir_fecha(filtros.get("fecha_desde"))
    fecha_hasta = convertir_fecha(filtros.get("fecha_hasta"))

    if fecha_desde:
        query = query.filter(CRVMovimiento.fecha >= fecha_desde)

    if fecha_hasta:
        query = query.filter(CRVMovimiento.fecha <= fecha_hasta)

    mes = filtros.get("mes", "")
    if mes:
        try:
            anio_texto, mes_texto = mes.split("-")
            query = query.filter(
                db.extract("year", CRVMovimiento.fecha) == int(anio_texto),
                db.extract("month", CRVMovimiento.fecha) == int(mes_texto)
            )
        except (ValueError, TypeError):
            pass

    anio = filtros.get("anio", "")
    if anio.isdigit():
        query = query.filter(
            db.extract("year", CRVMovimiento.fecha) == int(anio)
        )

    tipo = filtros.get("tipo", "")
    if tipo:
        query = query.filter(CRVMovimiento.tipo == tipo)

    tercero = filtros.get("tercero", "")
    if tercero:
        patron = f"%{tercero}%"
        query = query.filter(
            db.or_(
                CRVMovimiento.tercero_nombre.ilike(patron),
                CRVMovimiento.tercero_identificacion.ilike(patron)
            )
        )

    proyecto = filtros.get("proyecto", "")
    if proyecto:
        query = query.filter(
            CRVMovimiento.proyecto.ilike(f"%{proyecto}%")
        )

    centro_costo = filtros.get("centro_costo", "")
    if centro_costo:
        query = query.filter(
            CRVMovimiento.centro_costo.ilike(f"%{centro_costo}%")
        )

    return query

def _aplicar_filtros_cxp(query, filtros):
    fecha_desde = convertir_fecha(filtros.get("fecha_desde"))
    fecha_hasta = convertir_fecha(filtros.get("fecha_hasta"))

    if fecha_desde:
        query = query.filter(CRVCuentaPagar.fecha_documento >= fecha_desde)

    if fecha_hasta:
        query = query.filter(CRVCuentaPagar.fecha_documento <= fecha_hasta)

    mes = filtros.get("mes", "")
    if mes:
        try:
            anio_texto, mes_texto = mes.split("-")
            query = query.filter(
                db.extract("year", CRVCuentaPagar.fecha_documento) == int(anio_texto),
                db.extract("month", CRVCuentaPagar.fecha_documento) == int(mes_texto)
            )
        except (ValueError, TypeError):
            pass

    anio = filtros.get("anio", "")
    if anio.isdigit():
        query = query.filter(
            db.extract("year", CRVCuentaPagar.fecha_documento) == int(anio)
        )

    tercero = filtros.get("tercero", "")
    if tercero:
        patron = f"%{tercero}%"
        query = query.join(
            CRVTercero,
            CRVCuentaPagar.proveedor_id == CRVTercero.id
        ).filter(
            db.or_(
                CRVTercero.razon_social.ilike(patron),
                CRVTercero.identificacion.ilike(patron)
            )
        )

    proyecto = filtros.get("proyecto", "")
    if proyecto:
        query = query.filter(
            CRVCuentaPagar.proyecto.ilike(f"%{proyecto}%")
        )

    centro_costo = filtros.get("centro_costo", "")
    if centro_costo:
        query = query.filter(
            CRVCuentaPagar.centro_costo.ilike(f"%{centro_costo}%")
        )

    return query

def _calcular_resumen_reporte(movimientos, cuentas):
    ingresos = 0.0
    compras = 0.0
    gasto_general = 0.0
    nomina = 0.0
    anticipos = 0.0
    prestamos = 0.0
    otros = 0.0

    for movimiento in movimientos:
        tipo = str(movimiento.tipo or "").strip().upper()
        valor = float(movimiento.valor_neto or movimiento.valor or 0)

        if tipo == "INGRESO":
            ingresos += valor
        elif tipo == "COMPRA":
            compras += valor
        elif tipo == "GASTO":
            gasto_general += valor
        elif tipo in ("NOMINA AFILIADOS", "NÓMINA AFILIADOS", "NOMINA OBRA", "NÓMINA OBRA"):
            nomina += valor
        elif tipo == "ANTICIPO":
            anticipos += valor
        elif tipo in ("PRESTAMO EMPLEADO", "PRÉSTAMO EMPLEADO"):
            prestamos += valor
        elif tipo in (
            "TRANSFERENCIA",
            "PAGO CUENTA POR PAGAR",
            "SALDO INICIAL CUENTA",
            "COBRO CUENTA POR COBRAR",
        ):
            pass
        else:
            otros += valor

    gastos = gasto_general + nomina + anticipos + prestamos + otros
    egresos = compras + gastos
    resultado = ingresos - egresos

    cxp_facturado = sum(float(c.valor_neto or 0) for c in cuentas)
    cxp_pagado = sum(float(c.total_pagado or 0) for c in cuentas)
    cxp_pendiente = sum(float(c.saldo_pendiente or 0) for c in cuentas)
    cxp_vencido = sum(
        float(c.saldo_pendiente or 0)
        for c in cuentas
        if c.estado == "VENCIDA"
    )

    return {
        "ingresos": ingresos,
        "compras": compras,
        "gastos": gastos,
        "nomina": nomina,
        "anticipos": anticipos,
        "prestamos": prestamos,
        "otros": otros,
        "egresos": egresos,
        "resultado": resultado,
        "cxp_facturado": cxp_facturado,
        "cxp_pagado": cxp_pagado,
        "cxp_pendiente": cxp_pendiente,
        "cxp_vencido": cxp_vencido,
        "cantidad_movimientos": len(movimientos),
        "cantidad_cxp": len(cuentas),
    }

def _datos_reportes_crv(empresa_id, filtros):
    mov_query = CRVMovimiento.query.filter_by(empresa_id=empresa_id)
    mov_query = _aplicar_filtros_movimientos(mov_query, filtros)
    movimientos = mov_query.order_by(
        CRVMovimiento.fecha.asc(),
        CRVMovimiento.id.asc()
    ).all()

    cxp_query = CRVCuentaPagar.query.filter_by(empresa_id=empresa_id)
    cxp_query = _aplicar_filtros_cxp(cxp_query, filtros)
    cuentas = cxp_query.order_by(
        CRVCuentaPagar.fecha_documento.asc(),
        CRVCuentaPagar.id.asc()
    ).all()

    terceros = CRVTercero.query.filter_by(
        empresa_id=empresa_id
    ).order_by(CRVTercero.razon_social.asc()).all()

    resumen = _calcular_resumen_reporte(movimientos, cuentas)
    iva_resumen = resumen_iva_movimientos(movimientos)

    # Resumen por proveedor basado en CxP.
    proveedor_map = {}
    for cuenta in cuentas:
        proveedor = cuenta.proveedor
        clave = proveedor.id if proveedor else f"SIN-{cuenta.id}"
        if clave not in proveedor_map:
            proveedor_map[clave] = {
                "nombre": proveedor.razon_social if proveedor else "SIN PROVEEDOR",
                "identificacion": proveedor.identificacion if proveedor else "",
                "facturado": 0.0,
                "pagado": 0.0,
                "saldo": 0.0,
                "vencido": 0.0,
            }
        fila = proveedor_map[clave]
        fila["facturado"] += float(cuenta.valor_neto or 0)
        fila["pagado"] += float(cuenta.total_pagado or 0)
        fila["saldo"] += float(cuenta.saldo_pendiente or 0)
        if cuenta.estado == "VENCIDA":
            fila["vencido"] += float(cuenta.saldo_pendiente or 0)

    proveedores_resumen = sorted(
        proveedor_map.values(),
        key=lambda x: x["nombre"].upper()
    )

    # Resumen por proyecto / centro de costo con impacto contable.
    proyectos_map = {}
    tipos_sin_impacto = {
        "TRANSFERENCIA",
        "PAGO CUENTA POR PAGAR",
        "SALDO INICIAL CUENTA",
        "COBRO CUENTA POR COBRAR",
    }
    for movimiento in movimientos:
        tipo = str(movimiento.tipo or "").strip().upper()
        if tipo in tipos_sin_impacto or tipo == "INGRESO":
            continue
        proyecto = (movimiento.proyecto or "SIN PROYECTO").strip() or "SIN PROYECTO"
        centro = (movimiento.centro_costo or "SIN CENTRO DE COSTO").strip() or "SIN CENTRO DE COSTO"
        clave = (proyecto, centro)
        if clave not in proyectos_map:
            proyectos_map[clave] = {
                "proyecto": proyecto,
                "centro_costo": centro,
                "total": 0.0,
                "movimientos": 0,
            }
        proyectos_map[clave]["total"] += float(
            movimiento.valor_neto or movimiento.valor or 0
        )
        proyectos_map[clave]["movimientos"] += 1

    proyectos_resumen = sorted(
        proyectos_map.values(),
        key=lambda x: (x["proyecto"].upper(), x["centro_costo"].upper())
    )

    return {
        "movimientos": movimientos,
        "cuentas": cuentas,
        "terceros": terceros,
        "resumen": resumen,
        "iva_resumen": iva_resumen,
        "proveedores_resumen": proveedores_resumen,
        "proyectos_resumen": proyectos_resumen,
    }

def _periodo_texto(filtros):
    if filtros.get("fecha_desde") or filtros.get("fecha_hasta"):
        return f"{filtros.get('fecha_desde') or 'Inicio'} a {filtros.get('fecha_hasta') or 'Hoy'}"
    if filtros.get("mes"):
        return filtros["mes"]
    if filtros.get("anio"):
        return filtros["anio"]
    return "Todos los registros"

def _nombre_cuenta_valido(valor):
    nombre = str(valor or "").strip()
    if not nombre:
        return ""
    if nombre.upper() in (
        "CUENTAS POR PAGAR",
        "CUENTAS POR COBRAR",
    ):
        return ""
    return nombre

def _valor_movimiento_bancario(movimiento):
    return float(
        movimiento.valor_neto
        or movimiento.valor
        or 0
    )

def _cuentas_financieras_crv(empresa_id):
    """
    Obtiene las cuentas financieras usadas por CRV sin crear
    una tabla adicional. Esto permite que los pagos ya registrados,
    movimientos históricos y transferencias aparezcan en el módulo.
    """
    movimientos = CRVMovimiento.query.filter_by(
        empresa_id=empresa_id
    ).order_by(
        CRVMovimiento.fecha.asc(),
        CRVMovimiento.id.asc()
    ).all()

    cuentas = {}

    for m in movimientos:
        tipo = str(m.tipo or "").strip().upper()

        # La cuenta de origen sí representa una cuenta propia de CRV.
        origen = _nombre_cuenta_valido(m.cuenta)

        if origen and origen not in cuentas:
            cuentas[origen] = {
                "nombre": origen,
                "saldo": 0.0,
                "ingresos": 0.0,
                "egresos": 0.0,
                "transferencias_entrada": 0.0,
                "transferencias_salida": 0.0,
                "movimientos": 0,
                "sin_conciliar": 0,
            }

        # La cuenta destino SOLO se considera cuenta propia cuando
        # el movimiento es una transferencia interna entre cuentas CRV.
        # En pagos a proveedores, cuenta_destino corresponde a la cuenta
        # bancaria del proveedor y NO debe aparecer como cuenta de la empresa.
        if tipo == "TRANSFERENCIA":
            destino = _nombre_cuenta_valido(m.cuenta_destino)

            if destino and destino not in cuentas:
                cuentas[destino] = {
                    "nombre": destino,
                    "saldo": 0.0,
                    "ingresos": 0.0,
                    "egresos": 0.0,
                    "transferencias_entrada": 0.0,
                    "transferencias_salida": 0.0,
                    "movimientos": 0,
                    "sin_conciliar": 0,
                }

    for m in movimientos:
        tipo = str(m.tipo or "").strip().upper()
        origen = _nombre_cuenta_valido(m.cuenta)
        destino = _nombre_cuenta_valido(m.cuenta_destino)
        valor = _valor_movimiento_bancario(m)

        if tipo == "SALDO INICIAL CUENTA":
            if origen:
                cuentas[origen]["saldo"] += valor
                cuentas[origen]["ingresos"] += valor
                cuentas[origen]["movimientos"] += 1
                if not bool(m.revisado):
                    cuentas[origen]["sin_conciliar"] += 1
            continue

        if tipo in ("INGRESO", "COBRO CUENTA POR COBRAR"):
            if origen:
                cuentas[origen]["saldo"] += valor
                cuentas[origen]["ingresos"] += valor
                cuentas[origen]["movimientos"] += 1
                if not bool(m.revisado):
                    cuentas[origen]["sin_conciliar"] += 1
            continue

        if tipo == "TRANSFERENCIA":
            if origen:
                cuentas[origen]["saldo"] -= valor
                cuentas[origen]["transferencias_salida"] += valor
                cuentas[origen]["movimientos"] += 1
                if not bool(m.revisado):
                    cuentas[origen]["sin_conciliar"] += 1

            if destino:
                cuentas[destino]["saldo"] += valor
                cuentas[destino]["transferencias_entrada"] += valor
                cuentas[destino]["movimientos"] += 1
                if not bool(m.revisado):
                    cuentas[destino]["sin_conciliar"] += 1
            continue

        # La COMPRA de una CxP no mueve banco al registrarse.
        if tipo == "COMPRA":
            forma_pago = str(m.forma_pago or "").strip().upper()
            if forma_pago in ("CREDITO", "CRÉDITO") or not origen:
                continue

        # Todos los demás movimientos con cuenta de origen
        # representan salida real de esa cuenta.
        if origen:
            cuentas[origen]["saldo"] -= valor
            cuentas[origen]["egresos"] += valor
            cuentas[origen]["movimientos"] += 1
            if not bool(m.revisado):
                cuentas[origen]["sin_conciliar"] += 1

    return sorted(
        cuentas.values(),
        key=lambda x: x["nombre"].upper()
    )

def _movimiento_es_bancario(movimiento):
    tipo = str(movimiento.tipo or "").strip().upper()

    # Todo movimiento con cuenta de origen pertenece al control bancario.
    if _nombre_cuenta_valido(movimiento.cuenta):
        return True

    # Una cuenta destino solo pertenece al control bancario cuando se trata
    # de una transferencia interna entre cuentas propias de CRV.
    if (
        tipo == "TRANSFERENCIA"
        and _nombre_cuenta_valido(movimiento.cuenta_destino)
    ):
        return True

    return False

def _impacto_movimiento_cuenta(movimiento, cuenta_nombre):
    """
    Retorna el impacto de un movimiento en una cuenta concreta.
    Positivo = entrada.
    Negativo = salida.
    """
    tipo = str(movimiento.tipo or "").strip().upper()
    origen = _nombre_cuenta_valido(movimiento.cuenta)
    destino = _nombre_cuenta_valido(movimiento.cuenta_destino)
    valor = _valor_movimiento_bancario(movimiento)

    impacto = 0.0

    if tipo == "SALDO INICIAL CUENTA":
        if origen == cuenta_nombre:
            impacto += valor
        return impacto

    if tipo in ("INGRESO", "COBRO CUENTA POR COBRAR"):
        if origen == cuenta_nombre:
            impacto += valor
        return impacto

    if tipo == "TRANSFERENCIA":
        if origen == cuenta_nombre:
            impacto -= valor
        if destino == cuenta_nombre:
            impacto += valor
        return impacto

    if tipo == "COMPRA":
        forma_pago = str(movimiento.forma_pago or "").strip().upper()
        if forma_pago in ("CREDITO", "CRÉDITO"):
            return 0.0

    if origen == cuenta_nombre:
        impacto -= valor

    return impacto

__all__ = ['_aplicar_filtros_cxp', '_aplicar_filtros_movimientos', '_calcular_resumen_reporte', '_cuentas_financieras_crv', '_datos_reportes_crv', '_impacto_movimiento_cuenta', '_movimiento_es_bancario', '_nombre_cuenta_valido', '_periodo_texto', '_reporte_filtros', '_valor_movimiento_bancario']
