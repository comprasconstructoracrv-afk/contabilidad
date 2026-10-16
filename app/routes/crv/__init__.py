"""Compatibility entry point for CRV routes.

Shared CRV helpers live in :mod:`crv_core`; route handlers are grouped by feature.
"""

from .crv_core import *
from .crv_core import __all__ as _core_exports

from .crv_carga import carga_inteligente_procesar, carga_inteligente_guardar_masivo, carga_inteligente, carga_inteligente_revisar_archivo, carga_inteligente_ver_archivo, carga_inteligente_eliminar_archivo, carga_inteligente_eliminar_lote
from .crv_dashboard import dashboard
from .crv_movimientos import movimientos, nuevo_movimiento, editar_movimiento, eliminar_movimiento
from .crv_terceros import terceros, cambiar_estado_tercero, editar_tercero
from .crv_cuentas_pagar import cuentas_por_pagar, editar_cuenta_por_pagar, eliminar_cuenta_por_pagar, cuenta_por_pagar_detalle, pagar_cuenta_por_pagar, eliminar_pago_cuenta_por_pagar
from .crv_reportes import reportes_contador, reportes_contador_excel, reportes_contador_pdf, exportaciones_crv, movimientos_excel, movimiento_comprobante_pdf, movimientos_pdf, terceros_excel, terceros_pdf, cuentas_pagar_excel, cuentas_pagar_pdf, bancos_caja_excel, bancos_caja_pdf, cuentas_cobrar_excel, cuentas_cobrar_pdf, proyectos_excel_crv, proyectos_pdf_crv, cierre_mensual_excel, cierre_mensual_pdf, conciliacion_bancaria_excel, conciliacion_bancaria_pdf
from .crv_bancos import bancos_caja, bancos_caja_conciliar, bancos_caja_eliminar
from .crv_cuentas_cobrar import cuentas_por_cobrar, cuenta_cobrar_detalle, cuenta_cobrar_editar, cuenta_cobrar_eliminar, cuenta_cobrar_registrar_cobro, cuenta_cobrar_reversar_cobro
from .crv_proyectos import proyectos_crv, proyecto_detalle_crv, proyecto_editar_crv, proyecto_estado_crv, proyecto_eliminar_crv
from .crv_cierres import cierre_mensual_crv, cierre_mensual_reabrir
from .crv_conciliacion import conciliacion_bancaria_crv, conciliacion_bancaria_movimiento, conciliacion_bancaria_todo

__all__ = list(_core_exports) + ['carga_inteligente_procesar', 'carga_inteligente_guardar_masivo', 'carga_inteligente', 'carga_inteligente_revisar_archivo', 'carga_inteligente_ver_archivo', 'carga_inteligente_eliminar_archivo', 'carga_inteligente_eliminar_lote', 'dashboard', 'movimientos', 'nuevo_movimiento', 'editar_movimiento', 'eliminar_movimiento', 'terceros', 'cambiar_estado_tercero', 'editar_tercero', 'cuentas_por_pagar', 'editar_cuenta_por_pagar', 'eliminar_cuenta_por_pagar', 'cuenta_por_pagar_detalle', 'pagar_cuenta_por_pagar', 'eliminar_pago_cuenta_por_pagar', 'reportes_contador', 'reportes_contador_excel', 'reportes_contador_pdf', 'exportaciones_crv', 'movimientos_excel', 'movimiento_comprobante_pdf', 'movimientos_pdf', 'terceros_excel', 'terceros_pdf', 'cuentas_pagar_excel', 'cuentas_pagar_pdf', 'bancos_caja_excel', 'bancos_caja_pdf', 'cuentas_cobrar_excel', 'cuentas_cobrar_pdf', 'proyectos_excel_crv', 'proyectos_pdf_crv', 'cierre_mensual_excel', 'cierre_mensual_pdf', 'conciliacion_bancaria_excel', 'conciliacion_bancaria_pdf', 'bancos_caja', 'bancos_caja_conciliar', 'bancos_caja_eliminar', 'cuentas_por_cobrar', 'cuenta_cobrar_detalle', 'cuenta_cobrar_editar', 'cuenta_cobrar_eliminar', 'cuenta_cobrar_registrar_cobro', 'cuenta_cobrar_reversar_cobro', 'proyectos_crv', 'proyecto_detalle_crv', 'proyecto_editar_crv', 'proyecto_estado_crv', 'proyecto_eliminar_crv', 'cierre_mensual_crv', 'cierre_mensual_reabrir', 'conciliacion_bancaria_crv', 'conciliacion_bancaria_movimiento', 'conciliacion_bancaria_todo']
