from datetime import datetime, date

from app.extensions import db


class CRVCuentaCobrar(db.Model):
    __tablename__ = "crv_cuenta_cobrar"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False,
        index=True
    )

    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey("crv_tercero.id"),
        nullable=False,
        index=True
    )

    sede_id = db.Column(
        db.Integer,
        db.ForeignKey("sede.id"),
        nullable=True,
        index=True
    )

    tipo_documento = db.Column(db.String(60), nullable=True)
    numero_documento = db.Column(db.String(120), nullable=False, index=True)
    fecha_documento = db.Column(db.Date, nullable=False, index=True)
    fecha_vencimiento = db.Column(db.Date, nullable=True, index=True)

    concepto = db.Column(db.String(300), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)

    # IVA / valores tributarios
    base_gravable = db.Column(db.Float, nullable=False, default=0)
    tipo_iva = db.Column(db.String(30), nullable=False, default="NO_APLICA", index=True)
    tarifa_iva = db.Column(db.Float, nullable=False, default=0)
    valor_iva = db.Column(db.Float, nullable=False, default=0)

    # valor_bruto = total documento (base + IVA)
    valor_bruto = db.Column(db.Float, nullable=False, default=0)
    descuento = db.Column(db.Float, nullable=False, default=0)
    retencion = db.Column(db.Float, nullable=False, default=0)
    otros_descuentos = db.Column(db.Float, nullable=False, default=0)
    valor_neto = db.Column(db.Float, nullable=False, default=0)

    total_cobrado = db.Column(db.Float, nullable=False, default=0)
    saldo_pendiente = db.Column(db.Float, nullable=False, default=0)

    categoria = db.Column(db.String(120), nullable=True, index=True)
    subcategoria = db.Column(db.String(120), nullable=True)
    proyecto = db.Column(db.String(150), nullable=True, index=True)
    centro_costo = db.Column(db.String(150), nullable=True, index=True)
    obra = db.Column(db.String(150), nullable=True)

    estado = db.Column(db.String(30), nullable=False, default="PENDIENTE", index=True)
    observaciones = db.Column(db.Text, nullable=True)
    origen_registro = db.Column(db.String(80), nullable=False, default="SISTEMA")
    usuario_registro = db.Column(db.String(120), nullable=True)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    fecha_actualizacion = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    empresa = db.relationship(
        "Empresa",
        backref=db.backref("crv_cuentas_cobrar", lazy=True)
    )

    cliente = db.relationship(
        "CRVTercero",
        backref=db.backref("cuentas_cobrar", lazy=True)
    )

    sede = db.relationship(
        "Sede",
        backref=db.backref("crv_cuentas_cobrar", lazy=True)
    )

    cobros = db.relationship(
        "CRVCobroCuentaCobrar",
        back_populates="cuenta_cobrar",
        cascade="all, delete-orphan",
        lazy=True
    )

    @property
    def total_documento(self):
        return float(self.valor_bruto or 0)

    def recalcular_iva(self):
        base = float(self.base_gravable or 0)
        tipo = str(self.tipo_iva or "NO_APLICA").strip().upper()
        tarifa = float(self.tarifa_iva or 0)
        if tipo == "NO_APLICA":
            self.tarifa_iva = 0
            self.valor_iva = 0
        else:
            self.valor_iva = round(base * tarifa / 100, 2)
        self.valor_bruto = round(base + float(self.valor_iva or 0), 2)

    @property
    def valor_calculado(self):
        bruto = float(self.valor_bruto or 0)
        descuento = float(self.descuento or 0)
        retencion = float(self.retencion or 0)
        otros = float(self.otros_descuentos or 0)
        return max(0, bruto - descuento - retencion - otros)

    def recalcular_saldos(self):
        self.valor_neto = self.valor_calculado
        self.total_cobrado = sum(
            float(c.valor_cobrado or 0)
            for c in self.cobros
        )
        self.saldo_pendiente = max(
            0,
            float(self.valor_neto or 0) - float(self.total_cobrado or 0)
        )
        self.recalcular_estado()

    def recalcular_estado(self):
        saldo = float(self.saldo_pendiente or 0)

        if saldo <= 0:
            self.estado = "COBRADA"
            return

        if self.fecha_vencimiento and self.fecha_vencimiento < date.today():
            self.estado = "VENCIDA"
            return

        if float(self.total_cobrado or 0) > 0:
            self.estado = "PARCIAL"
            return

        self.estado = "PENDIENTE"

    @property
    def dias_vencida(self):
        if (
            self.fecha_vencimiento
            and float(self.saldo_pendiente or 0) > 0
            and self.fecha_vencimiento < date.today()
        ):
            return (date.today() - self.fecha_vencimiento).days
        return 0

    @property
    def esta_vencida(self):
        return (
            self.fecha_vencimiento is not None
            and float(self.saldo_pendiente or 0) > 0
            and self.fecha_vencimiento < date.today()
        )

    def __repr__(self):
        return (
            f"<CRVCuentaCobrar id={self.id} "
            f"documento={self.numero_documento} "
            f"saldo={self.saldo_pendiente}>"
        )
