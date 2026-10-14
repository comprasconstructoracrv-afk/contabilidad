from datetime import datetime

from app.extensions import db


class CRVPagoCuentaPagar(db.Model):
    __tablename__ = "crv_pago_cuenta_pagar"

    id = db.Column(db.Integer, primary_key=True)

    # ============================================================
    # EMPRESA / OBLIGACIÓN
    # ============================================================

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False,
        index=True
    )

    cuenta_pagar_id = db.Column(
        db.Integer,
        db.ForeignKey("crv_cuenta_pagar.id"),
        nullable=False,
        index=True
    )

    # ============================================================
    # FECHA / VALOR
    # ============================================================

    fecha = db.Column(
        db.Date,
        nullable=False,
        index=True
    )

    valor_pagado = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    # ============================================================
    # FORMA DE PAGO
    # ============================================================

    forma_pago = db.Column(
        db.String(80),
        nullable=True
    )

    cuenta_origen = db.Column(
        db.String(150),
        nullable=True,
        index=True
    )

    cuenta_destino = db.Column(
        db.String(180),
        nullable=True
    )

    beneficiario = db.Column(
        db.String(180),
        nullable=True
    )

    referencia_pago = db.Column(
        db.String(120),
        nullable=True
    )

    numero_soporte = db.Column(
        db.String(120),
        nullable=True
    )

    # ============================================================
    # VÍNCULO CON MOVIMIENTO CONTABLE
    # ============================================================

    movimiento_id = db.Column(
        db.Integer,
        db.ForeignKey("crv_movimiento.id"),
        nullable=True,
        index=True
    )

    # ============================================================
    # CONTROL
    # ============================================================

    observaciones = db.Column(
        db.Text,
        nullable=True
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

    # ============================================================
    # RELACIONES
    # ============================================================

    empresa = db.relationship(
        "Empresa",
        backref=db.backref(
            "crv_pagos_cuentas_pagar",
            lazy=True
        )
    )

    cuenta_pagar = db.relationship(
        "CRVCuentaPagar",
        back_populates="pagos"
    )

    movimiento = db.relationship(
        "CRVMovimiento",
        backref=db.backref(
            "pagos_cuentas_pagar",
            lazy=True
        )
    )

    def __repr__(self):
        return (
            f"<CRVPagoCuentaPagar "
            f"id={self.id} "
            f"cuenta_pagar_id={self.cuenta_pagar_id} "
            f"valor={self.valor_pagado}>"
        )