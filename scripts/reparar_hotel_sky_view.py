from app import create_app
from app.extensions import db
from app.models.hotel_venta_accion import HotelVentaAccion
from app.models.hotel_pago_accion import HotelPagoAccion
from app.models.movimiento import Movimiento

app = create_app()


def reparar_hotel():
    with app.app_context():
        empresa_id = 4  # HOTEL SKY VIEW según tu captura

        ventas = HotelVentaAccion.query.filter_by(empresa_id=empresa_id).order_by(
            HotelVentaAccion.fecha.asc(),
            HotelVentaAccion.id.asc()
        ).all()

        consecutivo_venta = 1
        for venta in ventas:
            venta.consecutivo_venta = consecutivo_venta
            consecutivo_venta += 1

        pagos = HotelPagoAccion.query.filter_by(empresa_id=empresa_id).order_by(
            HotelPagoAccion.fecha.asc(),
            HotelPagoAccion.id.asc()
        ).all()

        consecutivo_recibo = 1
        for pago in pagos:
            pago.consecutivo_recibo = consecutivo_recibo
            consecutivo_recibo += 1

        movimientos = Movimiento.query.filter(
            Movimiento.empresa_id == empresa_id,
            Movimiento.categoria.in_(["VENTA ACCIONES HOTEL", "RECIBO CAJA HOTEL"])
        ).all()

        for movimiento in movimientos:
            db.session.delete(movimiento)

        db.session.flush()

        pagos = HotelPagoAccion.query.filter_by(empresa_id=empresa_id).order_by(
            HotelPagoAccion.fecha.asc(),
            HotelPagoAccion.id.asc()
        ).all()

        for pago in pagos:
            venta = pago.venta_accion
            movimiento = Movimiento(
                fecha=pago.fecha,
                tipo="INGRESO",
                categoria="VENTA ACCIONES HOTEL",
                cuenta=pago.entidad_pago if pago.entidad_pago else (pago.forma_pago or ""),
                tercero=venta.cliente,
                valor=float(pago.valor_pagado or 0),
                descripcion=f"HOTEL SKY VIEW RECIBO DE CAJA #{pago.consecutivo_recibo} - Venta #{venta.consecutivo_venta} - {venta.cliente}",
                empresa_id=venta.empresa_id,
                sede_id=venta.sede_id
            )
            db.session.add(movimiento)

        db.session.commit()
        print("HOTEL SKY VIEW reparado correctamente.")


if __name__ == "__main__":
    reparar_hotel()