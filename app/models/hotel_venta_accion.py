from app.extensions import db


class HotelVentaAccion(db.Model):
    __tablename__ = "hotel_venta_accion"

    id = db.Column(db.Integer, primary_key=True)

    fecha = db.Column(db.Date, nullable=False)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False
    )

    sede_id = db.Column(
        db.Integer,
        db.ForeignKey("sede.id"),
        nullable=True
    )

    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey("hotel_cliente.id"),
        nullable=True
    )

    consecutivo_venta = db.Column(db.Integer, nullable=False, default=1)

    # respaldo de datos del cliente en el momento de la venta
    cliente = db.Column(db.String(150), nullable=False)
    cliente_identificacion = db.Column(db.String(50), nullable=True)
    cliente_direccion = db.Column(db.String(200), nullable=True)
    cliente_telefono = db.Column(db.String(50), nullable=True)
    cliente_ciudad = db.Column(db.String(120), nullable=True)
    cliente_correo = db.Column(db.String(150), nullable=True)

    descripcion = db.Column(db.String(250), nullable=False)

    cantidad_acciones = db.Column(db.Integer, nullable=False, default=1)

    valor_unitario_lista = db.Column(db.Float, nullable=False, default=0)
    descuento = db.Column(db.Float, nullable=False, default=0)
    valor_unitario_final = db.Column(db.Float, nullable=False, default=0)

    valor_total_lista = db.Column(db.Float, nullable=False, default=0)
    valor_total_final = db.Column(db.Float, nullable=False, default=0)

    valor_inicial = db.Column(db.Float, nullable=False, default=0)
    valor_recibido = db.Column(db.Float, nullable=False, default=0)
    saldo_pendiente = db.Column(db.Float, nullable=False, default=0)

    financiado = db.Column(db.Boolean, nullable=False, default=False)
    numero_cuotas = db.Column(db.Integer, nullable=False, default=0)
    valor_cuota = db.Column(db.Float, nullable=False, default=0)
    fecha_primera_cuota = db.Column(db.Date, nullable=True)

    forma_pago = db.Column(db.String(80), nullable=True)
    entidad_pago = db.Column(db.String(120), nullable=True)
    cuenta_destino = db.Column(db.String(150), nullable=True)

    estado = db.Column(db.String(30), nullable=False, default="PENDIENTE")
    observacion = db.Column(db.String(300), nullable=True)

    empresa = db.relationship(
        "Empresa",
        backref=db.backref("ventas_acciones_hotel", lazy=True)
    )

    sede = db.relationship(
        "Sede",
        backref=db.backref("ventas_acciones_hotel", lazy=True)
    )

    cliente_rel = db.relationship(
        "HotelCliente",
        backref=db.backref("ventas", lazy=True)
    )

    @property
    def nombre_estado(self):
        if float(self.saldo_pendiente or 0) <= 0:
            return "PAGADA"

        if float(self.valor_recibido or 0) > 0:
            if self.financiado:
                return "FINANCIADA"
            return "ABONADA"

        return "PENDIENTE"

    def recalcular_estado(self):
        self.estado = self.nombre_estado

    def __repr__(self):
        return f"<HotelVentaAccion {self.id} cliente={self.cliente} acciones={self.cantidad_acciones}>"