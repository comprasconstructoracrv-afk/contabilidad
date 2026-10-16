"""CRV cuentas pagar service helpers."""

from ..crv_context import (
    CRVMovimiento,
    db,
    session,
)
from .validation import (
    _asignar_comprobante_permanente,
)

def obtener_movimiento_compra_cxp(
    empresa_id,
    cuenta_id
):

    return CRVMovimiento.query.filter_by(
        empresa_id=empresa_id,
        origen_registro="CUENTAS_POR_PAGAR",
        numero_soporte=f"CXP-{cuenta_id}"
    ).order_by(
        CRVMovimiento.id.asc()
    ).first()

def sincronizar_movimiento_compra_cxp(
    cuenta
):

    proveedor = cuenta.proveedor

    movimiento = obtener_movimiento_compra_cxp(
        cuenta.empresa_id,
        cuenta.id
    )

    if movimiento is None:

        movimiento = CRVMovimiento(
            empresa_id=cuenta.empresa_id,
            origen_registro="CUENTAS_POR_PAGAR",
            numero_soporte=f"CXP-{cuenta.id}",
            revisado=False,
            estado="ACTIVO"
        )

        db.session.add(movimiento)

    movimiento.sede_id = cuenta.sede_id
    movimiento.fecha = cuenta.fecha_documento
    movimiento.tipo = "COMPRA"
    movimiento.categoria = cuenta.categoria or "COMPRA"
    movimiento.subcategoria = cuenta.subcategoria or ""
    movimiento.concepto = cuenta.concepto
    movimiento.descripcion = (
        cuenta.descripcion
        or f"Cuenta por pagar {cuenta.numero_documento}"
    )

    movimiento.tercero_id = (
        proveedor.id
        if proveedor
        else None
    )

    movimiento.tercero_nombre = (
        proveedor.razon_social
        if proveedor
        else ""
    )

    movimiento.tercero_identificacion = (
        proveedor.identificacion
        if proveedor
        else ""
    )

    movimiento.tercero_direccion = (
        proveedor.direccion
        if proveedor
        else ""
    )

    movimiento.tercero_email = (
        proveedor.email
        if proveedor
        else ""
    )

    movimiento.tercero_telefono = (
        (
            proveedor.celular
            or proveedor.telefono
            or ""
        )
        if proveedor
        else ""
    )

    movimiento.tercero_contacto = (
        proveedor.contacto
        if proveedor
        else ""
    )

    movimiento.tipo_documento = cuenta.tipo_documento or ""
    movimiento.numero_documento = cuenta.numero_documento
    movimiento.numero_soporte = f"CXP-{cuenta.id}"
    movimiento.fecha_documento = cuenta.fecha_documento
    movimiento.fecha_vencimiento = cuenta.fecha_vencimiento

    movimiento.base_gravable = cuenta.base_gravable or 0
    movimiento.tipo_iva = cuenta.tipo_iva or "NO_APLICA"
    movimiento.tarifa_iva = cuenta.tarifa_iva or 0
    movimiento.valor_iva = cuenta.valor_iva or 0
    movimiento.valor = cuenta.valor_bruto or 0
    movimiento.descuento = cuenta.descuento or 0
    movimiento.retencion = cuenta.retencion or 0
    movimiento.otros_descuentos = cuenta.otros_descuentos or 0
    movimiento.valor_neto = cuenta.valor_neto or 0

    movimiento.forma_pago = "CREDITO"
    movimiento.cuenta = "CUENTAS POR PAGAR"
    movimiento.cuenta_destino = ""
    movimiento.beneficiario = (
        proveedor.razon_social
        if proveedor
        else ""
    )
    movimiento.referencia_pago = ""

    movimiento.proyecto = cuenta.proyecto or ""
    movimiento.centro_costo = cuenta.centro_costo or ""
    movimiento.obra = cuenta.obra or ""

    movimiento.observaciones = (
        "Registro automático sincronizado desde "
        f"la cuenta por pagar CXP-{cuenta.id}."
    )

    movimiento.origen_registro = "CUENTAS_POR_PAGAR"
    movimiento.estado = "ACTIVO"
    movimiento.usuario_registro = str(
        session.get(
            "usuario",
            ""
        )
    )

    _asignar_comprobante_permanente(
        movimiento
    )

    return movimiento

__all__ = ['obtener_movimiento_compra_cxp', 'sincronizar_movimiento_compra_cxp']
