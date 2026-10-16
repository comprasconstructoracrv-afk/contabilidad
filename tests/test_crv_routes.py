import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from flask import Flask
from reportlab.pdfgen.canvas import Canvas

from app.extensions import db
from app.models.empresa import Empresa
from app.models.crv_cuenta_pagar import CRVCuentaPagar
from app.models.crv_movimiento import CRVMovimiento
from app.models.crv_tercero import CRVTercero
from app.models.inventario_ecobike import InventarioEcobike
from app.models.movimiento_inventario_ecobike import MovimientoInventarioEcobike
from app.models.producto_ecobike import ProductoEcobike
from app.models.sede import Sede
from app.models.venta_ecobike import VentaEcobike
from app.routes.crv import (
    _analizar_factura_carga,
    _resumen_cierre_mes,
    crv_bp,
    proteger_crv,
)
from app.routes.crv.services.carga import (
    _extraer_nit_factura,
    _extraer_numero_factura,
    _extraer_proveedor_factura,
    _normalizar_identificacion_carga,
    _tipo_documento_factura,
    registrar_factura_carga_inteligente,
)


class CrvRouteContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = Flask(__name__)
        app.register_blueprint(crv_bp)
        cls.routes = {
            (
                rule.endpoint,
                rule.rule,
                frozenset(rule.methods - {"HEAD", "OPTIONS"}),
            )
            for rule in app.url_map.iter_rules()
            if rule.endpoint.startswith("crv.")
        }

    def test_all_crv_endpoints_are_registered(self):
        self.assertEqual(len(self.routes), 63)

    def test_main_crv_routes_keep_their_paths_and_methods(self):
        expected = {
            ("crv.dashboard", "/crv/", frozenset({"GET"})),
            ("crv.dashboard", "/crv/dashboard", frozenset({"GET"})),
            ("crv.carga_inteligente_guardar_masivo",
                "/crv/carga-inteligente/<lote_id>/guardar-masivo",
                frozenset({"POST"}),
            ),
            ("crv.carga_inteligente_aprobar_lote",
                "/crv/carga-inteligente/<lote_id>/aprobar",
                frozenset({"POST"}),
            ),
            ("crv.carga_inteligente_ver_archivo",
                "/crv/carga-inteligente/<lote_id>/archivo/<archivo_id>/ver",
                frozenset({"GET"}),
            ),
            ("crv.movimientos", "/crv/movimientos", frozenset({"GET"})),
            ("crv.cuentas_por_pagar", "/crv/cuentas-por-pagar", frozenset({"GET", "POST"})),
            ("crv.pagar_cuenta_por_pagar",
                "/crv/cuentas-por-pagar/<int:cuenta_id>/pagar",
                frozenset({"POST"}),
            ),
            ("crv.cuentas_por_cobrar",
                "/crv/cuentas-por-cobrar",
                frozenset({"GET", "POST"}),
            ),
            ("crv.proyectos_crv", "/crv/proyectos", frozenset({"GET", "POST"})),
            ("crv.cierre_mensual_crv", "/crv/cierre-mensual", frozenset({"GET", "POST"})),
            ("crv.conciliacion_bancaria_crv",
                "/crv/conciliacion-bancaria",
                frozenset({"GET", "POST"}),
            ),
            ("crv.reportes_contador_excel",
                "/crv/reportes-contador/excel",
                frozenset({"GET"}),
            ),
            ("crv.movimiento_comprobante_pdf",
                "/crv/movimientos/<int:movimiento_id>/comprobante-pdf",
                frozenset({"GET"}),
            ),
            ("crv.bancos_caja", "/crv/bancos-caja", frozenset({"GET", "POST"})),
        }

        self.assertTrue(expected <= self.routes)

    def test_shared_helpers_remain_available_from_the_compatibility_package(self):
        self.assertEqual(proteger_crv.__module__, "app.routes.crv.services.validation")
        self.assertEqual(_analizar_factura_carga.__module__, "app.routes.crv.services.carga")
        self.assertEqual(_resumen_cierre_mes.__module__, "app.routes.crv.services.cierres")


class SmartInvoiceExtractionTests(unittest.TestCase):
    def test_extracts_supplier_id_invoice_date_and_amounts_from_text_pdf(self):
        invoice_text = [
            "ACME SUMINISTROS S.A.S.",
            "NIT: 900.123.456-7",
            "Factura electrónica de venta No. FEV-123",
            "Fecha de emisión: 15/10/2026",
            "Subtotal: $ 1.000.000,00",
            "IVA 19%: $ 190.000,00",
            "Total a pagar: $ 1.190.000,00",
        ]

        with TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "invoice.pdf"
            canvas = Canvas(str(pdf_path))
            for index, line in enumerate(invoice_text):
                canvas.drawString(40, 800 - index * 20, line)
            canvas.save()

            result = _analizar_factura_carga(
                1,
                pdf_path,
                pdf_path.name,
            )

        self.assertEqual(result["proveedor"], "ACME SUMINISTROS S.A.S.")
        self.assertEqual(result["identificacion"], "900.123.456-7")
        self.assertEqual(result["tipo_documento_tercero"], "NIT")
        self.assertEqual(result["numero_documento"], "FEV-123")
        self.assertEqual(result["fecha_documento"], "2026-10-15")
        self.assertEqual(result["base_gravable"], 1_000_000)
        self.assertEqual(result["tarifa_iva"], 19)
        self.assertEqual(result["valor_iva"], 190_000)
        self.assertEqual(result["total_documento"], 1_190_000)
        self.assertEqual(result["estado"], "REVISION_REQUERIDA")

    def test_identification_parser_handles_cedula_labels_and_punctuation(self):
        text = "Identificación: 12.345.678\n"

        self.assertEqual(_extraer_nit_factura(text), "12.345.678")
        self.assertEqual(_tipo_documento_factura(text), "CEDULA")
        self.assertEqual(_normalizar_identificacion_carga("12.345.678"), "12345678")
        self.assertEqual(_extraer_proveedor_factura("PROVEEDOR: Empresa de Prueba"), "Empresa de Prueba")
        self.assertEqual(_extraer_numero_factura("N° Factura: FE-908"), "FE-908")


class SmartInvoiceArchiveTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.app = Flask(
            "crv-smart-invoice-archive-tests",
            instance_path=self.directory.name,
        )
        self.app.config["SECRET_KEY"] = "test-only"
        self.app.register_blueprint(crv_bp)
        self.client = self.app.test_client()

        self.lote_id = "lote-archivo"
        self.archivo_id = "archivo-123"
        self.lote_dir = (
            Path(self.directory.name)
            / "crv_carga_inteligente"
            / "7"
            / self.lote_id
        )
        self.lote_dir.mkdir(parents=True)
        (self.lote_dir / "archivo-123.pdf").write_bytes(b"%PDF test file")
        self.manifest_path = self.lote_dir / "lote.json"
        self.manifest = {
            "empresa_id": 7,
            "estado": "APROBADO",
            "archivos": [{
                "archivo_id": self.archivo_id,
                "nombre_guardado": "archivo-123.pdf",
                "nombre_original": "factura original.pdf",
            }],
        }
        self._save_manifest()

        with self.client.session_transaction() as session:
            session["usuario"] = "usuario-test"
            session["empresa_id"] = 7
            session["empresa_nombre"] = "CRV CONSTRUCTORA"

    def tearDown(self):
        self.directory.cleanup()

    def _save_manifest(self):
        self.manifest_path.write_text(
            json.dumps(self.manifest),
            encoding="utf-8",
        )

    def test_approved_invoice_is_served_inline_for_audit(self):
        response = self.client.get(
            f"/crv/carga-inteligente/{self.lote_id}/archivo/"
            f"{self.archivo_id}/ver"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertIn("inline", response.headers["Content-Disposition"])
        self.assertEqual(response.data, b"%PDF test file")
        self.assertEqual(
            response.headers["X-Content-Type-Options"],
            "nosniff",
        )
        response.close()

    def test_pending_lot_documents_cannot_be_viewed_from_archive_route(self):
        self.manifest["estado"] = "PENDIENTE_REVISION"
        self._save_manifest()

        response = self.client.get(
            f"/crv/carga-inteligente/{self.lote_id}/archivo/"
            f"{self.archivo_id}/ver"
        )

        self.assertEqual(response.status_code, 404)


class SmartInvoiceRegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask("crv-smart-invoice-tests")
        cls.app.config.update(
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SECRET_KEY="test-only",
        )
        db.init_app(cls.app)
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        cls.test_tables = [
            Empresa.__table__,
            Sede.__table__,
            ProductoEcobike.__table__,
            InventarioEcobike.__table__,
            MovimientoInventarioEcobike.__table__,
            VentaEcobike.__table__,
            CRVTercero.__table__,
            CRVCuentaPagar.__table__,
            CRVMovimiento.__table__,
        ]
        db.metadata.create_all(bind=db.engine, tables=cls.test_tables)
        cls.empresa = Empresa(nombre="CRV TEST")
        db.session.add(cls.empresa)
        db.session.commit()
        cls.empresa_id = cls.empresa.id

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        db.metadata.drop_all(bind=db.engine, tables=cls.test_tables)
        db.engine.dispose()
        cls.app_context.pop()

    def setUp(self):
        db.session.query(CRVMovimiento).delete()
        db.session.query(CRVCuentaPagar).delete()
        db.session.query(CRVTercero).delete()
        db.session.commit()

    def test_approval_creates_one_supplier_payable_and_linked_purchase(self):
        item = {
            "archivo_id": "abc123",
            "nombre_original": "factura.pdf",
            "proveedor": "Proveedor de Prueba S.A.S.",
            "identificacion": "900.123.456-7",
            "tipo_documento_tercero": "NIT",
            "numero_documento": "FEV-100",
            "fecha_documento": "2026-10-15",
            "base_gravable": 1_000_000,
            "tarifa_iva": 19,
            "tipo_iva": "DESCONTABLE",
            "valor_iva": 190_000,
            "total_documento": 1_190_000,
            "revision_manual": True,
            "duplicado": False,
        }

        with self.app.test_request_context("/"):
            first = registrar_factura_carga_inteligente(
                self.empresa_id,
                "lote-1",
                item,
            )
            db.session.commit()
            second = registrar_factura_carga_inteligente(
                self.empresa_id,
                "lote-1",
                item,
            )
            db.session.commit()

        self.assertEqual(first.id, second.id)
        self.assertEqual(CRVTercero.query.count(), 1)
        self.assertEqual(CRVCuentaPagar.query.count(), 1)
        self.assertEqual(CRVMovimiento.query.count(), 1)

        payable = CRVCuentaPagar.query.one()
        movement = CRVMovimiento.query.one()
        self.assertEqual(payable.proveedor.razon_social, item["proveedor"])
        self.assertEqual(payable.proveedor.identificacion, item["identificacion"])
        self.assertEqual(payable.valor_bruto, item["total_documento"])
        self.assertEqual(payable.tipo_iva, "DESCONTABLE")
        self.assertEqual(movement.tipo, "COMPRA")
        self.assertEqual(movement.tercero_id, payable.proveedor_id)
        self.assertEqual(movement.numero_documento, item["numero_documento"])
        self.assertEqual(movement.base_gravable, item["base_gravable"])
        self.assertEqual(movement.valor_iva, item["valor_iva"])
        self.assertEqual(movement.valor, item["total_documento"])

    def test_existing_supplier_is_reused_and_duplicate_invoice_is_rejected(self):
        supplier = CRVTercero(
            empresa_id=self.empresa_id,
            tipo_tercero="PROVEEDOR",
            tipo_documento="NIT",
            identificacion="9001234567",
            razon_social="Proveedor Existente",
        )
        db.session.add(supplier)
        db.session.commit()

        item = {
            "archivo_id": "abc124",
            "nombre_original": "factura.pdf",
            "proveedor": "Proveedor Existente",
            "identificacion": "900.123.456-7",
            "tipo_documento_tercero": "NIT",
            "numero_documento": "FEV-101",
            "fecha_documento": "2026-10-15",
            "base_gravable": 1_000,
            "tarifa_iva": 0,
            "tipo_iva": "NO_APLICA",
            "valor_iva": 0,
            "total_documento": 1_000,
            "revision_manual": True,
            "duplicado": False,
        }

        with self.app.test_request_context("/"):
            first = registrar_factura_carga_inteligente(
                self.empresa_id,
                "lote-2",
                item,
            )
            db.session.commit()
            duplicate = dict(item, archivo_id="abc125")
            with self.assertRaisesRegex(ValueError, "ya existe"):
                registrar_factura_carga_inteligente(
                    self.empresa_id,
                    "lote-2",
                    duplicate,
                )
            db.session.rollback()

        self.assertEqual(first.proveedor_id, supplier.id)
        self.assertEqual(CRVTercero.query.count(), 1)
        self.assertEqual(CRVCuentaPagar.query.count(), 1)
        self.assertEqual(CRVMovimiento.query.count(), 1)


if __name__ == "__main__":
    unittest.main()
