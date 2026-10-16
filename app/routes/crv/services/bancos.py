"""CRV bancos service helpers."""

from ..crv_context import (
    CRVConciliacionBancaria,
    CRVMovimiento,
    db,
)
from .reportes_data import (
    _nombre_cuenta_valido,
    _valor_movimiento_bancario,
)

def _impacto_bancario_movimiento(movimiento, cuenta):
    tipo = str(
        movimiento.tipo or ""
    ).strip().upper()

    origen = _nombre_cuenta_valido(
        movimiento.cuenta
    )

    destino = ""

    if tipo == "TRANSFERENCIA":
        destino = _nombre_cuenta_valido(
            movimiento.cuenta_destino
        )

    valor = _valor_movimiento_bancario(
        movimiento
    )

    impacto = 0.0

    if tipo == "SALDO INICIAL CUENTA":
        if origen == cuenta:
            impacto += valor
        return impacto

    if tipo == "INGRESO":
        if origen == cuenta:
            impacto += valor
        return impacto

    if tipo == "COBRO CUENTA POR COBRAR":
        if origen == cuenta:
            impacto += valor
        return impacto

    if tipo == "TRANSFERENCIA":
        if origen == cuenta:
            impacto -= valor

        if destino == cuenta:
            impacto += valor

        return impacto

    if tipo == "COMPRA":
        forma_pago = str(
            movimiento.forma_pago or ""
        ).strip().upper()

        if forma_pago in (
            "CREDITO",
            "CRÉDITO"
        ):
            return 0.0

    if origen == cuenta:
        impacto -= valor

    return impacto

def _saldo_cuenta_hasta(
    empresa_id,
    cuenta,
    fecha_fin
):
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

    return sum(
        _impacto_bancario_movimiento(
            movimiento,
            cuenta
        )
        for movimiento in movimientos
    )

def _movimientos_cuenta_periodo(
    empresa_id,
    cuenta,
    anio,
    mes
):
    movimientos = (
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

    return [
        movimiento
        for movimiento in movimientos
        if abs(
            _impacto_bancario_movimiento(
                movimiento,
                cuenta
            )
        ) > 0
    ]

def _conciliacion_periodo(
    empresa_id,
    cuenta,
    anio,
    mes
):
    return (
        CRVConciliacionBancaria.query
        .filter_by(
            empresa_id=empresa_id,
            cuenta=cuenta,
            anio=anio,
            mes=mes
        )
        .first()
    )

__all__ = ['_conciliacion_periodo', '_impacto_bancario_movimiento', '_movimientos_cuenta_periodo', '_saldo_cuenta_hasta']
