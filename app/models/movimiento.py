from app.extensions import db


class Movimiento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    categoria = db.Column(db.String(100), nullable=False)
    cuenta = db.Column(db.String(150), nullable=True)
    tercero = db.Column(db.String(150), nullable=True)
    valor = db.Column(db.Float, nullable=False)
    descripcion = db.Column(db.String(200), nullable=True)

    empresa_id = db.Column(db.Integer, db.ForeignKey("empresa.id"), nullable=False)
    sede_id = db.Column(db.Integer, db.ForeignKey("sede.id"), nullable=True)

    empresa = db.relationship("Empresa", backref=db.backref("movimientos", lazy=True))
    sede = db.relationship("Sede", backref=db.backref("movimientos", lazy=True))