from datetime import datetime

from app.extensions import db


class CRVTercero(db.Model):
    __tablename__ = "crv_tercero"

    id = db.Column(db.Integer, primary_key=True)

    # ============================================================
    # EMPRESA
    # ============================================================

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False,
        index=True
    )

    # ============================================================
    # CLASIFICACIÓN DEL TERCERO
    # ============================================================

    tipo_tercero = db.Column(
        db.String(40),
        nullable=False,
        default="TERCERO"
    )

    tipo_documento = db.Column(
        db.String(20),
        nullable=True
    )

    identificacion = db.Column(
        db.String(50),
        nullable=False,
        index=True
    )

    razon_social = db.Column(
        db.String(180),
        nullable=False
    )

    nombre_comercial = db.Column(
        db.String(180),
        nullable=True
    )

    # ============================================================
    # CONTACTO
    # ============================================================

    direccion = db.Column(
        db.String(250),
        nullable=True
    )

    ciudad = db.Column(
        db.String(120),
        nullable=True
    )

    departamento = db.Column(
        db.String(120),
        nullable=True
    )

    telefono = db.Column(
        db.String(60),
        nullable=True
    )

    celular = db.Column(
        db.String(60),
        nullable=True
    )

    email = db.Column(
        db.String(180),
        nullable=True
    )

    contacto = db.Column(
        db.String(150),
        nullable=True
    )

    # ============================================================
    # DATOS BANCARIOS
    # ============================================================

    banco = db.Column(
        db.String(120),
        nullable=True
    )

    tipo_cuenta = db.Column(
        db.String(40),
        nullable=True
    )

    numero_cuenta = db.Column(
        db.String(80),
        nullable=True
    )

    titular_cuenta = db.Column(
        db.String(180),
        nullable=True
    )

    # ============================================================
    # CONTROL
    # ============================================================

    observaciones = db.Column(
        db.Text,
        nullable=True
    )

    activo = db.Column(
        db.Boolean,
        nullable=False,
        default=True
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
            "crv_terceros",
            lazy=True
        )
    )

    movimientos = db.relationship(
        "CRVMovimiento",
        back_populates="tercero_rel",
        lazy=True
    )

    # ============================================================
    # PROPIEDADES
    # ============================================================

    @property
    def nombre_mostrar(self):
        if self.razon_social:
            return self.razon_social

        if self.nombre_comercial:
            return self.nombre_comercial

        return self.identificacion or ""

    def __repr__(self):
        return (
            f"<CRVTercero "
            f"id={self.id} "
            f"identificacion={self.identificacion} "
            f"razon_social={self.razon_social}>"
        )