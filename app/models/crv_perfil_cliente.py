from datetime import datetime
from app.extensions import db


class CRVPerfilCliente(db.Model):
    __tablename__ = "crv_perfil_cliente"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False,
        index=True,
    )
    tercero_id = db.Column(
        db.Integer,
        db.ForeignKey("crv_tercero.id"),
        nullable=False,
        index=True,
    )

    proyecto = db.Column(db.String(180), nullable=True, index=True)
    tipo_concepto_base = db.Column(
        db.String(80),
        nullable=False,
        default="VALOR_LOTE",
    )
    concepto_base_label = db.Column(
        db.String(150),
        nullable=True,
        default="Valor Lote",
    )

    valor_base = db.Column(db.Float, nullable=False, default=0.0)
    porcentaje_tramo_1 = db.Column(db.Float, nullable=False, default=100.0)
    porcentaje_tramo_2 = db.Column(db.Float, nullable=False, default=0.0)
    descuento = db.Column(db.Float, nullable=False, default=0.0)

    observaciones = db.Column(db.Text, nullable=True)
    activo = db.Column(db.Boolean, nullable=False, default=True, index=True)
    usuario_registro = db.Column(db.String(120), nullable=True)
    fecha_creacion = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    fecha_actualizacion = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    tercero = db.relationship("CRVTercero", lazy="joined")
    items = db.relationship(
        "CRVPerfilClienteItem",
        backref="perfil",
        cascade="all, delete-orphan",
        order_by="CRVPerfilClienteItem.orden.asc(), CRVPerfilClienteItem.id.asc()",
        lazy="joined",
    )
    adicionales = db.relationship(
        "CRVPerfilClienteAdicional",
        backref="perfil",
        cascade="all, delete-orphan",
        order_by="CRVPerfilClienteAdicional.orden.asc(), CRVPerfilClienteAdicional.id.asc()",
        lazy="joined",
    )


class CRVPerfilClienteItem(db.Model):
    __tablename__ = "crv_perfil_cliente_item"

    id = db.Column(db.Integer, primary_key=True)
    perfil_id = db.Column(
        db.Integer,
        db.ForeignKey("crv_perfil_cliente.id"),
        nullable=False,
        index=True,
    )
    # 'BASE' (Valor Lote, Valor Casa, etc.) o 'TRAMO' (Tramo 1 100%, Tramo 2 70%, etc.)
    categoria = db.Column(db.String(30), nullable=False, default="BASE")
    orden = db.Column(db.Integer, nullable=False, default=1)
    concepto = db.Column(db.String(200), nullable=False)
    porcentaje = db.Column(db.Float, nullable=False, default=0.0)
    valor = db.Column(db.Float, nullable=False, default=0.0)


class CRVPerfilClienteAdicional(db.Model):
    __tablename__ = "crv_perfil_cliente_adicional"

    id = db.Column(db.Integer, primary_key=True)
    perfil_id = db.Column(
        db.Integer,
        db.ForeignKey("crv_perfil_cliente.id"),
        nullable=False,
        index=True,
    )
    orden = db.Column(db.Integer, nullable=False, default=1)
    concepto = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Float, nullable=False, default=0.0)