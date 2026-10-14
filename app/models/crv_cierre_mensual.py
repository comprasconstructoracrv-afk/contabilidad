from datetime import datetime
from app.extensions import db


class CRVCierreMensual(db.Model):
    __tablename__ = "crv_cierre_mensual"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
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

    estado = db.Column(
        db.String(20),
        nullable=False,
        default="ABIERTO",
        index=True
    )

    ingresos = db.Column(db.Float, nullable=False, default=0)
    compras = db.Column(db.Float, nullable=False, default=0)
    gastos = db.Column(db.Float, nullable=False, default=0)
    resultado = db.Column(db.Float, nullable=False, default=0)

    cxp_facturado = db.Column(db.Float, nullable=False, default=0)
    cxp_pagado = db.Column(db.Float, nullable=False, default=0)
    cxp_pendiente = db.Column(db.Float, nullable=False, default=0)

    cxc_facturado = db.Column(db.Float, nullable=False, default=0)
    cxc_cobrado = db.Column(db.Float, nullable=False, default=0)
    cxc_pendiente = db.Column(db.Float, nullable=False, default=0)

    saldo_bancos_caja = db.Column(db.Float, nullable=False, default=0)

    movimientos_mes = db.Column(db.Integer, nullable=False, default=0)
    movimientos_sin_conciliar = db.Column(db.Integer, nullable=False, default=0)

    observaciones = db.Column(db.Text, nullable=True)

    usuario_cierre = db.Column(db.String(120), nullable=True)
    fecha_cierre = db.Column(db.DateTime, nullable=True)

    usuario_reapertura = db.Column(db.String(120), nullable=True)
    fecha_reapertura = db.Column(db.DateTime, nullable=True)
    motivo_reapertura = db.Column(db.Text, nullable=True)

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
            "anio",
            "mes",
            name="uq_crv_cierre_empresa_periodo"
        ),
    )

    empresa = db.relationship(
        "Empresa",
        backref=db.backref(
            "crv_cierres_mensuales",
            lazy=True
        )
    )

    @property
    def periodo_texto(self):
        return f"{self.anio}-{self.mes:02d}"

    @property
    def cerrado(self):
        return self.estado == "CERRADO"

    def __repr__(self):
        return (
            f"<CRVCierreMensual "
            f"id={self.id} "
            f"periodo={self.periodo_texto} "
            f"estado={self.estado}>"
        )
