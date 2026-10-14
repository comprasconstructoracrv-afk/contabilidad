from app.extensions import db


class EmpresaConfig(db.Model):
    __tablename__ = "empresa_config"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresa.id"),
        nullable=False,
        unique=True
    )

    nombre_comercial = db.Column(db.String(150), nullable=False)
    razon_social = db.Column(db.String(200), nullable=True)
    nit = db.Column(db.String(50), nullable=True)

    direccion = db.Column(db.String(200), nullable=True)
    ciudad = db.Column(db.String(120), nullable=True)
    telefono = db.Column(db.String(80), nullable=True)
    correo = db.Column(db.String(150), nullable=True)
    sitio_web = db.Column(db.String(150), nullable=True)

    logo_path = db.Column(db.String(200), nullable=True)

    color_primario = db.Column(db.String(20), nullable=False, default="#18293D")
    color_secundario = db.Column(db.String(20), nullable=False, default="#D4AF37")
    color_acento = db.Column(db.String(20), nullable=False, default="#16A34A")

    tipo_negocio = db.Column(db.String(50), nullable=False, default="GENERAL")

    prefijo_recibo = db.Column(db.String(30), nullable=False, default="RC")
    texto_nota_recibo = db.Column(db.Text, nullable=True)

    firma_elaborado_por = db.Column(db.String(120), nullable=True)
    firma_aprobado_por = db.Column(db.String(120), nullable=True)

    empresa = db.relationship(
        "Empresa",
        backref=db.backref("configuracion", uselist=False, lazy=True)
    )

    def __repr__(self):
        return f"<EmpresaConfig empresa_id={self.empresa_id} nombre={self.nombre_comercial}>"