"""CRV cuentas cobrar service helpers."""

from sqlalchemy import func

from ..crv_context import (
    CRVCobroCuentaCobrar,
    CRVMovimiento,
    CRVTercero,
    db,
    session,
)


def _clientes_crv(empresa_id):
    return CRVTercero.query.filter(
        CRVTercero.empresa_id == empresa_id,
        CRVTercero.activo == True,
        CRVTercero.tipo_tercero.in_([
            "CLIENTE",
            "CLIENTE_ECOBIKE",
            "TERCERO",
            "ENTIDAD",
            "OTRO",
        ])
    ).order_by(CRVTercero.razon_social.asc()).all()


def _capital_desde_movimiento(mov):
    """Obtiene el capital real del movimiento sin confundirlo con intereses o mora."""
    cap = float(mov.base_gravable or 0)
    inte = float(getattr(mov, "valor_intereses", 0) or 0)
    mora = float(getattr(mov, "valor_mora", 0) or 0)

    # Si base_gravable es 0 y tampoco tiene intereses/mora (ej. ingreso antiguo o importado), toma el neto
    if cap <= 0 and inte <= 0 and mora <= 0:
        cap = float(mov.valor_neto or mov.valor or 0)
    return round(max(0.0, cap), 2)


def _vincular_ingresos_existentes_cliente(cuenta):
    """Actualiza cobros ya vinculados si su movimiento cambió y vincula ingresos nuevos del cliente."""
    cliente = cuenta.cliente or (
        CRVTercero.query.get(cuenta.cliente_id) if cuenta.cliente_id else None
    )
    if not cliente:
        return 0

    identificacion = (cliente.identificacion or "").strip().upper()
    actualizados = 0

    # Limpiar cobros huérfanos cuyo movimiento ya fue eliminado en Movimientos
    for cobro_existente in list(cuenta.cobros):
        if cobro_existente.movimiento_id is not None and cobro_existente.movimiento is None:
            db.session.delete(cobro_existente)
    db.session.flush()
    cuenta.recalcular_saldos()


    for cobro_existente in list(cuenta.cobros):
        mov = cobro_existente.movimiento
        if not mov:
            continue

        mismo_cliente = (mov.tercero_id == cliente.id) or (
            identificacion
            and (mov.tercero_identificacion or "").strip().upper() == identificacion
        )
        es_ingreso_activo = (
            (mov.estado or "").upper() == "ACTIVO"
            and (mov.tipo or "").upper() in ("INGRESO", "COBRO CUENTA POR COBRAR")
        )

        if not mismo_cliente or not es_ingreso_activo:
            db.session.delete(cobro_existente)
            actualizados += 1
            continue

        nuevo_capital = _capital_desde_movimiento(mov)
        if round(float(cobro_existente.valor_cobrado or 0), 2) != nuevo_capital or cobro_existente.fecha != mov.fecha:
            cobro_existente.fecha = mov.fecha
            cobro_existente.valor_cobrado = nuevo_capital
            cobro_existente.forma_pago = mov.forma_pago or cobro_existente.forma_pago or ""
            cobro_existente.cuenta_receptora = mov.cuenta or cobro_existente.cuenta_receptora or ""
            cobro_existente.referencia_pago = mov.referencia_pago or cobro_existente.referencia_pago or ""
            cobro_existente.numero_soporte = mov.numero_soporte or mov.numero_documento or cobro_existente.numero_soporte or ""
            cobro_existente.observaciones = mov.observaciones or mov.concepto or cobro_existente.observaciones or ""
            actualizados += 1

    if actualizados > 0:
        db.session.flush()
        cuenta.recalcular_saldos()

    # 2. Vincular nuevos movimientos INGRESO del cliente que aún no estén asociados a ningún cobro
    cuenta.recalcular_saldos()
    if float(cuenta.saldo_pendiente or 0) <= 0:
        return actualizados

    ya_vinculados = (
        db.session.query(CRVCobroCuentaCobrar.movimiento_id)
        .filter(
            CRVCobroCuentaCobrar.empresa_id == cuenta.empresa_id,
            CRVCobroCuentaCobrar.movimiento_id.isnot(None),
        )
    )

    condiciones_cliente = [CRVMovimiento.tercero_id == cliente.id]
    if identificacion:
        condiciones_cliente.append(
            func.upper(func.trim(CRVMovimiento.tercero_identificacion)) == identificacion
        )

    movimientos_sueltos = (
        CRVMovimiento.query.filter(
            CRVMovimiento.empresa_id == cuenta.empresa_id,
            CRVMovimiento.estado == "ACTIVO",
            CRVMovimiento.tipo.in_(["INGRESO", "COBRO CUENTA POR COBRAR"]),
            ~CRVMovimiento.id.in_(ya_vinculados),
            ~func.coalesce(CRVMovimiento.origen_registro, "").like("CUENTA_POR_COBRAR:%"),
            db.or_(*condiciones_cliente),
        )
        .order_by(CRVMovimiento.fecha.asc(), CRVMovimiento.id.asc())
        .all()
    )

    vinculados = 0
    for mov in movimientos_sueltos:
        cuenta.recalcular_saldos()
        saldo_disponible = float(cuenta.saldo_pendiente or 0)
        if saldo_disponible <= 0:
            break

        capital_mov = _capital_desde_movimiento(mov)
        inte_mov = float(getattr(mov, "valor_intereses", 0) or 0)
        mora_mov = float(getattr(mov, "valor_mora", 0) or 0)

        # Permite vincular incluso si el pago fue solo de intereses o mora (capital = 0)
        if capital_mov <= 0 and inte_mov <= 0 and mora_mov <= 0:
            continue

        abono_capital = min(capital_mov, saldo_disponible)

        cobro = CRVCobroCuentaCobrar(
            empresa_id=cuenta.empresa_id,
            cuenta_cobrar_id=cuenta.id,
            movimiento_id=mov.id,
            fecha=mov.fecha,
            valor_cobrado=abono_capital,
            forma_pago=mov.forma_pago or "",
            cuenta_receptora=mov.cuenta or "",
            cuenta_origen_cliente="",
            pagador=mov.tercero_nombre or cliente.razon_social or "",
            referencia_pago=mov.referencia_pago or "",
            numero_soporte=mov.numero_soporte or mov.numero_documento or "",
            observaciones=mov.observaciones or mov.concepto or "Ingreso vinculado desde Movimientos.",
            usuario_registro=str(session.get("usuario", "")),
        )
        db.session.add(cobro)
        vinculados += 1

    if vinculados > 0:
        db.session.flush()
        cuenta.recalcular_saldos()

    return actualizados + vinculados

def _sincronizar_movimiento_cxc(cuenta):
    # Limpia si existía un movimiento previo de creación para evitar duplicar ingresos
    movimiento_previo = CRVMovimiento.query.filter_by(
        empresa_id=cuenta.empresa_id,
        origen_registro=f"CUENTA_POR_COBRAR:{cuenta.id}"
    ).first()
    if movimiento_previo:
        db.session.delete(movimiento_previo)

    # Vincula automáticamente los ingresos previos que el cliente ya tenía en Movimientos
    _vincular_ingresos_existentes_cliente(cuenta)
    return None


__all__ = [
    "_clientes_crv",
    "_sincronizar_movimiento_cxc",
    "_vincular_ingresos_existentes_cliente",
]