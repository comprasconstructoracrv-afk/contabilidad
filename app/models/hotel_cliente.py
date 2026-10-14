from app.extensions import db


class HotelCliente(db.Model):
    __tablename__ = "hotel_cliente"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False
    )

    nombre = db.Column(db.String(150), nullable=False)
    identificacion = db.Column(db.String(50), nullable=True, index=True)
    direccion = db.Column(db.String(200), nullable=True)
    telefono = db.Column(db.String(50), nullable=True)
    ciudad = db.Column(db.String(120), nullable=True)
    correo = db.Column(db.String(150), nullable=True)

    activo = db.Column(db.Boolean, nullable=False, default=True)

    empresa = db.relationship(
        "Empresa",
        backref=db.backref("clientes_hotel", lazy=True)
    )

    __table_args__ = (
        db.UniqueConstraint(
            "empresa_id",
            "identificacion",
            name="uq_hotel_cliente_empresa_identificacion"
        ),
    )

    def __repr__(self):
        return f"<HotelCliente {self.id} {self.nombre}>"