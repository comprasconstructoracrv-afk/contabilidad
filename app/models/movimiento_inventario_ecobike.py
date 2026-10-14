from datetime import datetime
from app.extensions import db


class MovimientoInventarioEcobike(db.Model):
    __tablename__ = "movimiento_inventario_ecobike"

    id = db.Column(db.Integer, primary_key=True)

    fecha = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    empresa_id = db.Column(db.Integer, db.ForeignKey("empresa.id"), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey("producto_ecobike.id"), nullable=False)

    sede_origen_id = db.Column(db.Integer, db.ForeignKey("sede.id"), nullable=True)
    sede_destino_id = db.Column(db.Integer, db.ForeignKey("sede.id"), nullable=True)

    tipo_movimiento = db.Column(db.String(40), nullable=False)
    # ENTRADA / TRASLADO / VENTA / AJUSTE / SALIDA

    cantidad = db.Column(db.Integer, nullable=False, default=0)

    observacion = db.Column(db.String(250), nullable=True)

    empresa = db.relationship(
        "Empresa",
        foreign_keys=[empresa_id],
        backref=db.backref("movimientos_inventario_ecobike", lazy=True)
    )

    producto = db.relationship(
        "ProductoEcobike",
        foreign_keys=[producto_id],
        backref=db.backref("movimientos_inventario_ecobike", lazy=True)
    )

    sede_origen = db.relationship(
        "Sede",
        foreign_keys=[sede_origen_id],
        backref=db.backref("movimientos_inventario_origen_ecobike", lazy=True)
    )

    sede_destino = db.relationship(
        "Sede",
        foreign_keys=[sede_destino_id],
        backref=db.backref("movimientos_inventario_destino_ecobike", lazy=True)
    )

    def __repr__(self):
        return f"<MovimientoInventarioEcobike {self.tipo_movimiento} producto={self.producto_id}>"