from datetime import datetime
from app.extensions import db


class CRVProyecto(db.Model):
    __tablename__ = "crv_proyecto"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False,
        index=True
    )

    codigo = db.Column(
        db.String(60),
        nullable=False,
        index=True
    )

    nombre = db.Column(
        db.String(180),
        nullable=False,
        index=True
    )

    tipo = db.Column(
        db.String(80),
        nullable=True
    )

    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey("crv_tercero.id"),
        nullable=True,
        index=True
    )

    ubicacion = db.Column(
        db.String(220),
        nullable=True
    )

    fecha_inicio = db.Column(
        db.Date,
        nullable=True,
        index=True
    )

    fecha_fin_estimada = db.Column(
        db.Date,
        nullable=True,
        index=True
    )

    presupuesto = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    valor_contrato = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    responsable = db.Column(
        db.String(180),
        nullable=True
    )

    centro_costo = db.Column(
        db.String(150),
        nullable=True,
        index=True
    )

    estado = db.Column(
        db.String(30),
        nullable=False,
        default="ACTIVO",
        index=True
    )

    descripcion = db.Column(
        db.Text,
        nullable=True
    )

    observaciones = db.Column(
        db.Text,
        nullable=True
    )

    activo = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
        index=True
    )

    usuario_registro = db.Column(
        db.String(120),
        nullable=True
    )

    fecha_creacion = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    fecha_actualizacion = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    empresa = db.relationship(
        "Empresa",
        backref=db.backref(
            "crv_proyectos",
            lazy=True
        )
    )

    cliente = db.relationship(
        "CRVTercero",
        backref=db.backref(
            "crv_proyectos_cliente",
            lazy=True
        )
    )

    def __repr__(self):
        return (
            f"<CRVProyecto "
            f"id={self.id} "
            f"codigo={self.codigo} "
            f"nombre={self.nombre}>"
        )
