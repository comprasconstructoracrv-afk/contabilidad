from datetime import datetime
from app.extensions import db


class CRVConciliacionBancaria(db.Model):
    __tablename__ = "crv_conciliacion_bancaria"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False,
        index=True
    )

    cuenta = db.Column(
        db.String(180),
        nullable=False,
        index=True
    )

    anio = db.Column(
        db.Integer,
        nullable=False,
        index=True
    )

    mes = db.Column(
        db.Integer,
        nullable=False,
        index=True
    )

    saldo_extracto = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    saldo_sistema = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    diferencia = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    estado = db.Column(
        db.String(30),
        nullable=False,
        default="PENDIENTE",
        index=True
    )

    observaciones = db.Column(
        db.Text,
        nullable=True
    )

    usuario_registro = db.Column(
        db.String(120),
        nullable=True
    )

    fecha_conciliacion = db.Column(
        db.DateTime,
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

    __table_args__ = (
        db.UniqueConstraint(
            "empresa_id",
            "cuenta",
            "anio",
            "mes",
            name="uq_crv_conciliacion_cuenta_periodo"
        ),
    )

    empresa = db.relationship(
        "Empresa",
        backref=db.backref(
            "crv_conciliaciones_bancarias",
            lazy=True
        )
    )

    @property
    def periodo_texto(self):
        return f"{self.anio}-{self.mes:02d}"

    def __repr__(self):
        return (
            f"<CRVConciliacionBancaria "
            f"cuenta={self.cuenta} "
            f"periodo={self.periodo_texto} "
            f"estado={self.estado}>"
        )
