from datetime import datetime, date

from app.extensions import db


class CRVCuentaPagar(db.Model):
    __tablename__ = "crv_cuenta_pagar"

    id = db.Column(db.Integer, primary_key=True)

    # ============================================================
    # EMPRESA / PROVEEDOR
    # ============================================================

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False,
        index=True
    )

    proveedor_id = db.Column(
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

    # ============================================================
    # DOCUMENTO
    # ============================================================

    tipo_documento = db.Column(
        db.String(60),
        nullable=True
    )

    numero_documento = db.Column(
        db.String(120),
        nullable=False,
        index=True
    )

    fecha_documento = db.Column(
        db.Date,
        nullable=False,
        index=True
    )

    fecha_vencimiento = db.Column(
        db.Date,
        nullable=True,
        index=True
    )

    concepto = db.Column(
        db.String(300),
        nullable=False
    )

    descripcion = db.Column(
        db.Text,
        nullable=True
    )

    # ============================================================
    # IVA / VALORES TRIBUTARIOS
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

    # ============================================================
    # VALORES
    # ============================================================

    # valor_bruto = total documento (base + IVA)
    valor_bruto = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    descuento = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    retencion = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    otros_descuentos = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    valor_neto = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    total_pagado = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    saldo_pendiente = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    # ============================================================
    # CLASIFICACIÓN
    # ============================================================

    categoria = db.Column(
        db.String(120),
        nullable=True,
        index=True
    )

    subcategoria = db.Column(
        db.String(120),
        nullable=True
    )

    proyecto = db.Column(
        db.String(150),
        nullable=True,
        index=True
    )

    centro_costo = db.Column(
        db.String(150),
        nullable=True,
        index=True
    )

    obra = db.Column(
        db.String(150),
        nullable=True
    )

    # ============================================================
    # CONTROL
    # ============================================================

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

    origen_registro = db.Column(
        db.String(80),
        nullable=False,
        default="SISTEMA"
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

    # ============================================================
    # RELACIONES
    # ============================================================

    empresa = db.relationship(
        "Empresa",
        backref=db.backref(
            "crv_cuentas_pagar",
            lazy=True
        )
    )

    proveedor = db.relationship(
        "CRVTercero",
        backref=db.backref(
            "cuentas_pagar",
            lazy=True
        )
    )

    sede = db.relationship(
        "Sede",
        backref=db.backref(
            "crv_cuentas_pagar",
            lazy=True
        )
    )

    pagos = db.relationship(
        "CRVPagoCuentaPagar",
        back_populates="cuenta_pagar",
        cascade="all, delete-orphan",
        lazy=True
    )

    # ============================================================
    # CÁLCULOS
    # ============================================================

    @property
    def total_documento(self):
        return float(
            self.valor_bruto or 0
        )

    @property
    def valor_calculado(self):
        return max(
            0,
            float(self.valor_bruto or 0)
            - float(self.descuento or 0)
            - float(self.retencion or 0)
            - float(self.otros_descuentos or 0)
        )

    def recalcular_iva(self):
        """
        Recalcula IVA y total del documento.

        Tratamientos sin valor de IVA:
        - NO_APLICA
        - EXENTO
        - EXCLUIDO

        Los demás tratamientos calculan IVA usando
        la tarifa registrada.
        """

        base = float(
            self.base_gravable or 0
        )

        tipo = str(
            self.tipo_iva or "NO_APLICA"
        ).strip().upper()

        tarifa = float(
            self.tarifa_iva or 0
        )

        if tipo in (
            "NO_APLICA",
            "EXENTO",
            "EXCLUIDO"
        ):
            self.tarifa_iva = 0
            self.valor_iva = 0

        else:
            tarifa = max(
                0,
                tarifa
            )

            self.tarifa_iva = tarifa

            self.valor_iva = round(
                base * tarifa / 100,
                2
            )

        self.valor_bruto = round(
            base
            + float(self.valor_iva or 0),
            2
        )

    def recalcular_saldos(self):
        self.valor_neto = self.valor_calculado

        total_pagado = sum(
            float(p.valor_pagado or 0)
            for p in self.pagos
        )

        self.total_pagado = total_pagado

        self.saldo_pendiente = max(
            0,
            float(self.valor_neto or 0)
            - total_pagado
        )

        self.recalcular_estado()

    def recalcular_estado(self):
        saldo = float(
            self.saldo_pendiente or 0
        )

        if saldo <= 0:
            self.estado = "PAGADA"
            return

        if (
            self.fecha_vencimiento
            and self.fecha_vencimiento < date.today()
        ):
            self.estado = "VENCIDA"
            return

        if float(
            self.total_pagado or 0
        ) > 0:
            self.estado = "PARCIAL"
            return

        self.estado = "PENDIENTE"

    @property
    def dias_vencida(self):
        if (
            self.fecha_vencimiento
            and self.saldo_pendiente
            and self.saldo_pendiente > 0
            and self.fecha_vencimiento < date.today()
        ):
            return (
                date.today()
                - self.fecha_vencimiento
            ).days

        return 0

    @property
    def esta_vencida(self):
        return (
            self.fecha_vencimiento is not None
            and float(
                self.saldo_pendiente or 0
            ) > 0
            and self.fecha_vencimiento < date.today()
        )

    def __repr__(self):
        return (
            f"<CRVCuentaPagar "
            f"id={self.id} "
            f"documento={self.numero_documento} "
            f"saldo={self.saldo_pendiente}>"
        )
