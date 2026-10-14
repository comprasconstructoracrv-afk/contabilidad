from app.extensions import db


class DocumentoConsecutivo(db.Model):
    __tablename__ = "documento_consecutivo"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False
    )

    tipo_documento = db.Column(db.String(60), nullable=False)
    siguiente_numero = db.Column(db.Integer, nullable=False, default=1)

    empresa = db.relationship(
        "Empresa",
        backref=db.backref("consecutivos_documento", lazy=True)
    )

    __table_args__ = (
        db.UniqueConstraint(
            "empresa_id",
            "tipo_documento",
            name="uq_empresa_tipo_documento"
        ),
    )

    def __repr__(self):
        return f"<DocumentoConsecutivo empresa_id={self.empresa_id} tipo={self.tipo_documento} siguiente={self.siguiente_numero}>"