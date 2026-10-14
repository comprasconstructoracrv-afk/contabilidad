from app.extensions import db


class ProductoEcobike(db.Model):
    __tablename__ = "producto_ecobike"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(db.Integer, db.ForeignKey("empresa.id"), nullable=False)

    tipo_producto = db.Column(db.String(30), nullable=False, default="BICICLETA")
    # BICICLETA / REPUESTO

    referencia = db.Column(db.String(150), nullable=False)

    marca = db.Column(db.String(100), nullable=True)
    modelo = db.Column(db.String(100), nullable=True)
    color = db.Column(db.String(80), nullable=True)
    talla = db.Column(db.String(50), nullable=True)
    serial = db.Column(db.String(120), nullable=True)

    costo_compra = db.Column(db.Float, nullable=False, default=0)
    precio_venta = db.Column(db.Float, nullable=False, default=0)

    stock_minimo = db.Column(db.Integer, nullable=False, default=0)

    activo = db.Column(db.Boolean, nullable=False, default=True)

    empresa = db.relationship(
        "Empresa",
        backref=db.backref("productos_ecobike", lazy=True)
    )

    @property
    def nombre_tipo(self):
        if self.tipo_producto == "REPUESTO":
            return "Repuesto"
        return "Bicicleta"

    @property
    def margen_estimado(self):
        return float(self.precio_venta or 0) - float(self.costo_compra or 0)

    def __repr__(self):
        return f"<ProductoEcobike {self.tipo_producto} - {self.referencia}>"