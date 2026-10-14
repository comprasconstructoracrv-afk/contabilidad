from app.extensions import db


class HotelPagoAccion(db.Model):
    __tablename__ = "hotel_pago_accion"

    id = db.Column(db.Integer, primary_key=True)

    fecha = db.Column(db.Date, nullable=False)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False
    )

    venta_accion_id = db.Column(
        db.Integer,
        db.ForeignKey("hotel_venta_accion.id"),
        nullable=False
    )

    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey("hotel_cliente.id"),
        nullable=True
    )

    consecutivo_recibo = db.Column(db.Integer, nullable=False, default=1)

    descripcion = db.Column(db.String(250), nullable=False)

    cantidad_acciones = db.Column(db.Integer, nullable=False, default=0)
    valor_pagado = db.Column(db.Float, nullable=False, default=0)
    saldo_resultante = db.Column(db.Float, nullable=False, default=0)

    forma_pago = db.Column(db.String(80), nullable=True)
    entidad_pago = db.Column(db.String(120), nullable=True)
    cuenta_destino = db.Column(db.String(150), nullable=True)

    cuota_aplicada_numero = db.Column(db.Integer, nullable=True)
    observacion = db.Column(db.String(300), nullable=True)

    empresa = db.relationship(
        "Empresa",
        backref=db.backref("pagos_acciones_hotel", lazy=True)
    )

    venta_accion = db.relationship(
        "HotelVentaAccion",
        backref=db.backref("pagos", lazy=True, cascade="all, delete-orphan")
    )

    cliente_rel = db.relationship(
        "HotelCliente",
        backref=db.backref("pagos", lazy=True)
    )

    def __repr__(self):
        return f"<HotelPagoAccion {self.id} venta={self.venta_accion_id} valor={self.valor_pagado}>"