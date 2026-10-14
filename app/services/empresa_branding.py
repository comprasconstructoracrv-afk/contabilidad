from app.extensions import db
from app.models.empresa import Empresa
from app.models.empresa_config import EmpresaConfig
from app.models.documento_consecutivo import DocumentoConsecutivo


TIPOS_DOCUMENTO_VALIDOS = {
    "RECIBO_CAJA",
    "VENTA_ACCION_HOTEL",
    "RECIBO_CAJA_HOTEL",
    "VENTA_ECOBIKE",
    "RECIBO_ECOBIKE",
}


def obtener_config_empresa(empresa_id):
    config = EmpresaConfig.query.filter_by(empresa_id=empresa_id).first()

    if config:
        return config

    empresa = Empresa.query.get(empresa_id)
    if not empresa:
        return None

    config = EmpresaConfig(
        empresa_id=empresa.id,
        nombre_comercial=empresa.nombre,
        razon_social=empresa.nombre,
        tipo_negocio="GENERAL",
        color_primario="#18293D",
        color_secundario="#D4AF37",
        color_acento="#16A34A",
        prefijo_recibo="RC",
    )
    db.session.add(config)
    db.session.commit()
    return config


def obtener_o_crear_consecutivo(empresa_id, tipo_documento):
    if tipo_documento not in TIPOS_DOCUMENTO_VALIDOS:
        raise ValueError(f"Tipo de documento no permitido: {tipo_documento}")

    consecutivo = DocumentoConsecutivo.query.filter_by(
        empresa_id=empresa_id,
        tipo_documento=tipo_documento
    ).first()

    if consecutivo:
        return consecutivo

    consecutivo = DocumentoConsecutivo(
        empresa_id=empresa_id,
        tipo_documento=tipo_documento,
        siguiente_numero=1
    )
    db.session.add(consecutivo)
    db.session.commit()
    return consecutivo


def tomar_siguiente_numero(empresa_id, tipo_documento):
    consecutivo = obtener_o_crear_consecutivo(empresa_id, tipo_documento)

    numero = consecutivo.siguiente_numero
    consecutivo.siguiente_numero += 1

    db.session.commit()
    return numero