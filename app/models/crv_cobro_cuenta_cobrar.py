from datetime import datetime

from app.extensions import db


class CRVCobroCuentaCobrar(db.Model):
    __tablename__ = "crv_cobro_cuenta_cobrar"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False,
        index=True
    )

    cuenta_cobrar_id = db.Column(
        db.Integer,
        db.ForeignKey("crv_cuenta_cobrar.id"),
        nullable=False,
        index=True
    )

    fecha = db.Column(db.Date, nullable=False, index=True)
    valor_cobrado = db.Column(db.Float, nullable=False, default=0)

    forma_pago = db.Column(db.String(80), nullable=True)
    cuenta_receptora = db.Column(db.String(150), nullable=True, index=True)
    cuenta_origen_cliente = db.Column(db.String(180), nullable=True)
    pagador = db.Column(db.String(180), nullable=True)
    referencia_pago = db.Column(db.String(120), nullable=True)
    numero_soporte = db.Column(db.String(120), nullable=True)

    movimiento_id = db.Column(
        db.Integer,
        db.ForeignKey("crv_movimiento.id"),
        nullable=True,
        index=True
    )

    observaciones = db.Column(db.Text, nullable=True)
    usuario_registro = db.Column(db.String(120), nullable=True)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    empresa = db.relationship(
        "Empresa",
        backref=db.backref("crv_cobros_cuentas_cobrar", lazy=True)
    )

    cuenta_cobrar = db.relationship(
        "CRVCuentaCobrar",
        back_populates="cobros"
    )

    movimiento = db.relationship(
        "CRVMovimiento",
        backref=db.backref("cobros_cuentas_cobrar", lazy=True)
    )

    def __repr__(self):
        return (
            f"<CRVCobroCuentaCobrar id={self.id} "
            f"cuenta_cobrar_id={self.cuenta_cobrar_id} "
            f"valor={self.valor_cobrado}>"
        )
