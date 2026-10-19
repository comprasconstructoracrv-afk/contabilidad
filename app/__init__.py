import os

from flask import Flask
from app.extensions import db

# ============================================================
# MODELOS GENERALES
# ============================================================

from app.models.empresa import Empresa
from app.models.sede import Sede
from app.models.movimiento import Movimiento
from app.models.venta_ecobike import VentaEcobike
from app.models.empresa_config import EmpresaConfig
from app.models.documento_consecutivo import DocumentoConsecutivo

# ============================================================
# MODELOS HOTEL SKY VIEW
# ============================================================

from app.models.hotel_cliente import HotelCliente
from app.models.hotel_venta_accion import HotelVentaAccion
from app.models.hotel_cuota import HotelCuota
from app.models.hotel_pago_accion import HotelPagoAccion

# ============================================================
# MODELOS CRV CONSTRUCTORA
# ============================================================

from app.models.crv_tercero import CRVTercero
from app.models.crv_movimiento import CRVMovimiento
from app.models.crv_cuenta_pagar import CRVCuentaPagar
from app.models.crv_pago_cuenta_pagar import CRVPagoCuentaPagar
from app.models.crv_cuenta_cobrar import CRVCuentaCobrar
from app.models.crv_cobro_cuenta_cobrar import CRVCobroCuentaCobrar
from app.models.crv_proyecto import CRVProyecto
from app.models.crv_cierre_mensual import CRVCierreMensual
from app.models.crv_conciliacion_bancaria import CRVConciliacionBancaria

from app.migraciones_crv import migrar_iva_crv


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "clave_secreta_123")

    database_url = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///contabilidad.db")
    
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    # ========================================================
    # BLUEPRINTS
    # ========================================================

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.movimientos import movimientos_bp
    from app.routes.reportes import reportes_bp
    from app.routes.empresas import empresas_bp
    from app.routes.sedes import sedes_bp
    from app.routes.ventas_ecobike import ventas_ecobike_bp
    from app.routes.reportes_ecobike import reportes_ecobike_bp
    from app.routes.hotel_sky_view import hotel_sky_view_bp
    from app.routes.hotel_cierre import hotel_cierre_bp
    from app.routes.ecobike_inventario import ecobike_inventario_bp

    # CRV CONSTRUCTORA
    from app.routes.crv import crv_bp

    # ========================================================
    # REGISTRO BLUEPRINTS
    # ========================================================

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(movimientos_bp)
    app.register_blueprint(reportes_bp)
    app.register_blueprint(empresas_bp)
    app.register_blueprint(sedes_bp)
    app.register_blueprint(ventas_ecobike_bp)
    app.register_blueprint(reportes_ecobike_bp)
    app.register_blueprint(hotel_sky_view_bp)
    app.register_blueprint(hotel_cierre_bp)
    app.register_blueprint(ecobike_inventario_bp)

    # CRV CONSTRUCTORA
    app.register_blueprint(crv_bp)

    # Crea únicamente las tablas que todavía no existan.
    # No elimina ni modifica los registros actuales.
    with app.app_context():
        db.create_all()
        migrar_iva_crv()

    return app
