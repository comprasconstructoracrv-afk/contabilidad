"""CRV cuentas cobrar service helpers."""

from ..crv_context import (
    CRVMovimiento,
    CRVTercero,
    db,
    session,
)
from .validation import (
    _asignar_comprobante_permanente,
)

def _clientes_crv(empresa_id):
    return CRVTercero.query.filter(
        CRVTercero.empresa_id == empresa_id,
        CRVTercero.activo == True,
        CRVTercero.tipo_tercero.in_([
            "CLIENTE",
            "TERCERO",
            "ENTIDAD",
            "OTRO",
        ])
    ).order_by(CRVTercero.razon_social.asc()).all()

def _sincronizar_movimiento_cxc(cuenta):
    movimiento = CRVMovimiento.query.filter_by(
        empresa_id=cuenta.empresa_id,
        origen_registro=f"CUENTA_POR_COBRAR:{cuenta.id}"
    ).first()

    cliente = cuenta.cliente

    if movimiento is None:
        movimiento = CRVMovimiento(
            empresa_id=cuenta.empresa_id,
            origen_registro=f"CUENTA_POR_COBRAR:{cuenta.id}",
            usuario_registro=str(session.get("usuario", "")),
            estado="ACTIVO"
        )
        db.session.add(movimiento)

    movimiento.sede_id = cuenta.sede_id
    movimiento.fecha = cuenta.fecha_documento
    movimiento.tipo = "INGRESO"
    movimiento.categoria = cuenta.categoria or "VENTA / CUENTA POR COBRAR"
    movimiento.subcategoria = cuenta.subcategoria or ""
    movimiento.concepto = cuenta.concepto
    movimiento.descripcion = cuenta.descripcion or ""
    movimiento.tercero_id = cliente.id if cliente else None
    movimiento.tercero_nombre = cliente.razon_social if cliente else ""
    movimiento.tercero_identificacion = cliente.identificacion if cliente else ""
    movimiento.tercero_direccion = cliente.direccion if cliente else ""
    movimiento.tercero_email = cliente.email if cliente else ""
    movimiento.tercero_telefono = ((cliente.celular or cliente.telefono or "") if cliente else "")
    movimiento.tercero_contacto = cliente.contacto if cliente else ""
    movimiento.tipo_documento = cuenta.tipo_documento or "CUENTA POR COBRAR"
    movimiento.numero_documento = cuenta.numero_documento
    movimiento.numero_soporte = f"CXC-{cuenta.id}"
    movimiento.fecha_documento = cuenta.fecha_documento
    movimiento.fecha_vencimiento = cuenta.fecha_vencimiento
    movimiento.base_gravable = float(cuenta.base_gravable or 0)
    movimiento.tipo_iva = cuenta.tipo_iva or "NO_APLICA"
    movimiento.tarifa_iva = float(cuenta.tarifa_iva or 0)
    movimiento.valor_iva = float(cuenta.valor_iva or 0)
    movimiento.valor = float(cuenta.valor_bruto or 0)
    movimiento.descuento = float(cuenta.descuento or 0)
    movimiento.retencion = float(cuenta.retencion or 0)
    movimiento.otros_descuentos = float(cuenta.otros_descuentos or 0)
    movimiento.valor_neto = float(cuenta.valor_neto or 0)
    movimiento.forma_pago = "CREDITO"
    movimiento.cuenta = "CUENTAS POR COBRAR"
    movimiento.cuenta_destino = ""
    movimiento.beneficiario = "CRV CONSTRUCTORA"
    movimiento.referencia_pago = ""
    movimiento.proyecto = cuenta.proyecto or ""
    movimiento.centro_costo = cuenta.centro_costo or ""
    movimiento.obra = cuenta.obra or ""
    movimiento.observaciones = cuenta.observaciones or ""
    movimiento.revisado = False

    _asignar_comprobante_permanente(
        movimiento
    )

    return movimiento

__all__ = ['_clientes_crv', '_sincronizar_movimiento_cxc']
