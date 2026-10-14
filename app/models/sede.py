from app.extensions import db


class Sede(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresa.id"), nullable=False)

    empresa = db.relationship("Empresa", backref=db.backref("sedes", lazy=True))

    def __repr__(self):
        return f"<Sede {self.nombre}>"