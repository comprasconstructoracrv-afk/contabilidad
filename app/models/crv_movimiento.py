from datetime import datetime

from app.extensions import db


class CRVMovimiento(db.Model):
    __tablename__ = "crv_movimiento"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False,
        index=True
    )

    sede_id = db.Column(
        db.Integer,
        db.ForeignKey("sede.id"),
        nullable=True,
        index=True
    )

    fecha = db.Column(
        db.Date,
        nullable=False,
        index=True
    )

    tipo = db.Column(
        db.String(80),
        nullable=False,
        index=True
    )

    categoria = db.Column(
        db.String(120),
        nullable=True,
        index=True
    )

    subcategoria = db.Column(
        db.String(120),
        nullable=True
    )

    concepto = db.Column(
        db.String(300),
        nullable=False
    )

    descripcion = db.Column(
        db.Text,
        nullable=True
    )

    tercero_id = db.Column(
        db.Integer,
        db.ForeignKey("crv_tercero.id"),
        nullable=True,
        index=True
    )

    tercero_nombre = db.Column(db.String(220), nullable=True)
    tercero_identificacion = db.Column(db.String(80), nullable=True, index=True)
    tercero_direccion = db.Column(db.String(250), nullable=True)
    tercero_email = db.Column(db.String(180), nullable=True)
    tercero_telefono = db.Column(db.String(80), nullable=True)
    tercero_contacto = db.Column(db.String(180), nullable=True)

    tipo_documento = db.Column(db.String(80), nullable=True)
    numero_documento = db.Column(db.String(120), nullable=True, index=True)
    numero_soporte = db.Column(db.String(120), nullable=True, index=True)
    fecha_documento = db.Column(db.Date, nullable=True, index=True)
    fecha_vencimiento = db.Column(db.Date, nullable=True, index=True)

    # ============================================================
    # VALORES TRIBUTARIOS / IVA
    # ============================================================

    base_gravable = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    tipo_iva = db.Column(
        db.String(30),
        nullable=False,
        default="NO_APLICA",
        index=True
    )

    tarifa_iva = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    valor_iva = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    # valor = total documento (base + IVA)
    valor = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    descuento = db.Column(db.Float, nullable=False, default=0)
    retencion = db.Column(db.Float, nullable=False, default=0)
    otros_descuentos = db.Column(db.Float, nullable=False, default=0)
    valor_neto = db.Column(db.Float, nullable=False, default=0)

    forma_pago = db.Column(db.String(80), nullable=True)
    cuenta = db.Column(db.String(150), nullable=True, index=True)
    cuenta_destino = db.Column(db.String(180), nullable=True)
    beneficiario = db.Column(db.String(180), nullable=True)
    referencia_pago = db.Column(db.String(120), nullable=True)

    proyecto = db.Column(db.String(150), nullable=True, index=True)
    centro_costo = db.Column(db.String(150), nullable=True, index=True)
    obra = db.Column(db.String(150), nullable=True)

    observaciones = db.Column(db.Text, nullable=True)
    revisado = db.Column(db.Boolean, nullable=False, default=False, index=True)
    estado = db.Column(db.String(30), nullable=False, default="ACTIVO", index=True)
    origen_registro = db.Column(db.String(100), nullable=False, default="SISTEMA", index=True)
    usuario_registro = db.Column(db.String(120), nullable=True)

    # ============================================================
    # COMPROBANTE INDIVIDUAL PERMANENTE
    # ============================================================

    comprobante_tipo = db.Column(
        db.String(10),
        nullable=True,
        index=True
    )

    comprobante_consecutivo = db.Column(
        db.Integer,
        nullable=True,
        index=True
    )

    comprobante_codigo = db.Column(
        db.String(30),
        nullable=True,
        index=True
    )

    # ============================================================
    # COMPATIBILIDAD CON LA BASE HISTÓRICA
    # ============================================================

    fecha_registro = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
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
        backref=db.backref("crv_movimientos", lazy=True)
    )

    sede = db.relationship(
        "Sede",
        backref=db.backref("crv_movimientos", lazy=True)
    )

    tercero_rel = db.relationship(
        "CRVTercero",
        backref=db.backref("crv_movimientos", lazy=True)
    )

    @property
    def total_documento(self):
        return float(self.valor or 0)

    @property
    def valor_calculado(self):
        return max(
            0,
            float(self.valor or 0)
            - float(self.descuento or 0)
            - float(self.retencion or 0)
            - float(self.otros_descuentos or 0)
        )

    def recalcular_iva(self):
        base = float(self.base_gravable or 0)
        tipo = str(self.tipo_iva or "NO_APLICA").strip().upper()
        tarifa = float(self.tarifa_iva or 0)

        if tipo in (
            "NO_APLICA",
            "EXENTO",
            "EXCLUIDO"
        ):
            self.tarifa_iva = 0
            self.valor_iva = 0
        else:
            tarifa = max(0, tarifa)
            self.tarifa_iva = tarifa
            self.valor_iva = round(
                base * tarifa / 100,
                2
            )

        self.valor = round(
            base + float(self.valor_iva or 0),
            2
        )

        self.recalcular_valor_neto()

    def recalcular_valor_neto(self):
        self.valor_neto = self.valor_calculado

    @property
    def nombre_tercero(self):
        if self.tercero_rel:
            return self.tercero_rel.razon_social
        return self.tercero_nombre or ""

    @property
    def anio(self):
        return self.fecha.year if self.fecha else None

    @property
    def mes_numero(self):
        return self.fecha.month if self.fecha else None

    def __repr__(self):
        return (
            f"<CRVMovimiento id={self.id} "
            f"fecha={self.fecha} tipo={self.tipo} "
            f"valor={self.valor} "
            f"comprobante={self.comprobante_codigo}>"
        )
