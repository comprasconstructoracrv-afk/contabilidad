from app.extensions import db


class InventarioEcobike(db.Model):
    __tablename__ = "inventario_ecobike"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(db.Integer, db.ForeignKey("empresa.id"), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey("producto_ecobike.id"), nullable=False)

    sede_id = db.Column(db.Integer, db.ForeignKey("sede.id"), nullable=True)

    ubicacion = db.Column(db.String(30), nullable=False, default="SEDE")
    # BODEGA / SEDE

    cantidad = db.Column(db.Integer, nullable=False, default=0)

    empresa = db.relationship(
        "Empresa",
        backref=db.backref("inventarios_ecobike", lazy=True)
    )

    producto = db.relationship(
        "ProductoEcobike",
        backref=db.backref("inventarios_ecobike", lazy=True)
    )

    sede = db.relationship(
        "Sede",
        backref=db.backref("inventarios_ecobike", lazy=True)
    )

    @property
    def nombre_ubicacion(self):
        if self.ubicacion == "BODEGA":
            return "Bodega principal"
        if self.sede:
            return self.sede.nombre
        return "Sede sin definir"

    @property
    def stock_bajo(self):
        minimo = int(self.producto.stock_minimo or 0) if self.producto else 0
        return int(self.cantidad or 0) <= minimo

    def __repr__(self):
        return f"<InventarioEcobike producto={self.producto_id} cantidad={self.cantidad}>"