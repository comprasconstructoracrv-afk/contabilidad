from app.extensions import db


class HotelCuota(db.Model):
    __tablename__ = "hotel_cuota"

    id = db.Column(db.Integer, primary_key=True)

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

    numero_cuota = db.Column(db.Integer, nullable=False)
    fecha_vencimiento = db.Column(db.Date, nullable=False)

    valor_cuota = db.Column(db.Float, nullable=False, default=0)
    valor_pagado = db.Column(db.Float, nullable=False, default=0)
    saldo_cuota = db.Column(db.Float, nullable=False, default=0)

    estado = db.Column(db.String(30), nullable=False, default="PENDIENTE")
    observacion = db.Column(db.String(250), nullable=True)

    empresa = db.relationship(
        "Empresa",
        backref=db.backref("cuotas_hotel", lazy=True)
    )

    venta_accion = db.relationship(
        "HotelVentaAccion",
        backref=db.backref("cuotas", lazy=True, cascade="all, delete-orphan")
    )

    def recalcular_estado(self):
        if float(self.saldo_cuota or 0) <= 0:
            self.estado = "PAGADA"
        elif float(self.valor_pagado or 0) > 0:
            self.estado = "ABONADA"
        else:
            self.estado = "PENDIENTE"

    def __repr__(self):
        return f"<HotelCuota venta={self.venta_accion_id} cuota={self.numero_cuota}>"