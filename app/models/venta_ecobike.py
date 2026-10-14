from app.extensions import db


class VentaEcobike(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    fecha = db.Column(db.Date, nullable=False)

    empresa_id = db.Column(db.Integer, db.ForeignKey("empresa.id"), nullable=False)
    sede_id = db.Column(db.Integer, db.ForeignKey("sede.id"), nullable=True)

    producto_id = db.Column(db.Integer, db.ForeignKey("producto_ecobike.id"), nullable=True)

    referencia_manual = db.Column(db.String(150), nullable=True)
    costo_manual = db.Column(db.Float, nullable=True)

    cantidad = db.Column(db.Integer, nullable=False, default=1)
    precio_unitario = db.Column(db.Float, nullable=False)

    tipo_venta = db.Column(db.String(20), nullable=False)  # CONTADO, CREDITO, SEPARADO
    valor_recibido = db.Column(db.Float, nullable=False, default=0)
    saldo_pendiente = db.Column(db.Float, nullable=False, default=0)

    descuento = db.Column(db.Float, nullable=False, default=0)

    cuenta = db.Column(db.String(150), nullable=True)
    cliente = db.Column(db.String(150), nullable=True)
    cliente_cedula = db.Column(db.String(50), nullable=True)
    cliente_direccion = db.Column(db.String(200), nullable=True)
    cliente_celular = db.Column(db.String(50), nullable=True)
    cliente_correo = db.Column(db.String(120), nullable=True)

    observacion = db.Column(db.String(250), nullable=True)

    empresa = db.relationship("Empresa", backref=db.backref("ventas_ecobike", lazy=True))
    sede = db.relationship("Sede", backref=db.backref("ventas_ecobike", lazy=True))
    producto = db.relationship("ProductoEcobike", backref=db.backref("ventas", lazy=True))

    @property
    def referencia(self):
        if self.producto:
            return self.producto.referencia
        return self.referencia_manual or ""

    @property
    def costo_unitario(self):
        if self.costo_manual is not None:
            return self.costo_manual
        if self.producto:
            return self.producto.costo_compra
        return 0

    @property
    def valor_bruto(self):
        return (self.cantidad or 0) * (self.precio_unitario or 0)

    @property
    def valor_total(self):
        total = self.valor_bruto - (self.descuento or 0)
        return total if total >= 0 else 0

    @property
    def costo_total(self):
        return (self.cantidad or 0) * (self.costo_unitario or 0)

    @property
    def utilidad_bruta(self):
        return self.valor_total - self.costo_total

    def __repr__(self):
        return f"<VentaEcobike {self.id} - {self.referencia}>"