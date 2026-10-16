"""Compatibility facade for CRV shared services.

Feature-specific helpers live in :mod:`app.routes.crv.services`.
"""

from .crv_context import *
from .crv_context import __all__ as _context_exports

from .services.validation import (
    usuario_valido,
    empresa_crv_valida,
    proteger_crv,
    convertir_fecha,
    convertir_numero,
    convertir_porcentaje,
    calcular_iva_formulario,
    resumen_iva_movimientos,
    obtener_tercero_por_identificacion,
    crear_o_actualizar_tercero_desde_formulario,
    _tipo_comprobante_movimiento,
    _titulo_comprobante_por_prefijo,
    _asegurar_tabla_secuencias_comprobantes,
    _siguiente_consecutivo_comprobante,
    _asignar_comprobante_permanente,
)

from .services.carga import (
    EXTENSIONES_CARGA_INTELIGENTE,
    TAMANO_MAXIMO_ARCHIVO_CARGA,
    _carpeta_carga_inteligente,
    _ruta_lote_carga,
    _leer_manifest_carga,
    _guardar_manifest_carga,
    _listar_lotes_carga_inteligente,
    _archivo_carga_valido,
    _normalizar_identificacion_carga,
    _limpiar_texto_factura,
    _leer_texto_pdf,
    _encontrar_valor_despues_etiqueta,
    _extraer_fecha_factura,
    _extraer_nit_factura,
    _numero_factura_candidato_valido,
    _extraer_numero_factura,
    _extraer_tarifa_iva_factura,
    _extraer_valor_iva_factura,
    _extraer_total_factura,
    _extraer_base_factura,
    _proveedor_candidato_valido,
    _extraer_proveedor_factura,
    _buscar_tercero_por_identificacion_carga,
    _es_factura_duplicada_carga,
    _validar_valores_factura_carga,
    _estado_revision_carga,
    _limpiar_monto_colombiano,
    _extraer_montos_por_cuadrante_inferior,
    _analizar_factura_carga,
    _tipo_documento_factura,
    obtener_cuenta_carga_inteligente,
    registrar_factura_carga_inteligente,
)

from .services.cuentas_pagar import (
    obtener_movimiento_compra_cxp,
    sincronizar_movimiento_compra_cxp,
)

from .services.reportes_data import (
    _reporte_filtros,
    _aplicar_filtros_movimientos,
    _aplicar_filtros_cxp,
    _calcular_resumen_reporte,
    _datos_reportes_crv,
    _periodo_texto,
    _nombre_cuenta_valido,
    _valor_movimiento_bancario,
    _cuentas_financieras_crv,
    _movimiento_es_bancario,
    _impacto_movimiento_cuenta,
)

from .services.reportes_exports import (
    _excel_estilos_base,
    _excel_titulo,
    _excel_encabezado,
    _excel_moneda,
    _excel_auto_ancho,
    _enviar_excel,
    _pdf_estilos_crv,
    _pdf_encabezado_historia,
    _pdf_tabla,
    _enviar_pdf,
    _money_export,
    _texto_pdf_seguro,
)

from .services.cuentas_cobrar import (
    _clientes_crv,
    _sincronizar_movimiento_cxc,
)

from .services.proyectos import (
    _nombre_proyecto_normalizado,
    _movimientos_proyecto,
    _cuentas_pagar_proyecto,
    _cuentas_cobrar_proyecto,
    _resumen_proyecto,
    _clientes_proyectos_crv,
)

from .services.cierres import (
    _rango_mes,
    _cierre_periodo,
    _periodo_crv_cerrado,
    _movimientos_mes_crv,
    _saldo_financiero_hasta,
    _resumen_cierre_mes,
    _fecha_formulario_cierre,
    bloquear_periodos_cerrados_crv,
)

from .services.bancos import (
    _impacto_bancario_movimiento,
    _saldo_cuenta_hasta,
    _movimientos_cuenta_periodo,
    _conciliacion_periodo,
)

__all__ = list(_context_exports) + ['usuario_valido', 'empresa_crv_valida', 'proteger_crv', 'convertir_fecha', 'convertir_numero', 'convertir_porcentaje', 'calcular_iva_formulario', 'resumen_iva_movimientos', 'obtener_tercero_por_identificacion', 'crear_o_actualizar_tercero_desde_formulario', '_tipo_comprobante_movimiento', '_titulo_comprobante_por_prefijo', '_asegurar_tabla_secuencias_comprobantes', '_siguiente_consecutivo_comprobante', '_asignar_comprobante_permanente', 'EXTENSIONES_CARGA_INTELIGENTE', 'TAMANO_MAXIMO_ARCHIVO_CARGA', '_carpeta_carga_inteligente', '_ruta_lote_carga', '_leer_manifest_carga', '_guardar_manifest_carga', '_listar_lotes_carga_inteligente', '_archivo_carga_valido', '_normalizar_identificacion_carga', '_limpiar_texto_factura', '_leer_texto_pdf', '_encontrar_valor_despues_etiqueta', '_extraer_fecha_factura', '_extraer_nit_factura', '_numero_factura_candidato_valido', '_extraer_numero_factura', '_extraer_tarifa_iva_factura', '_extraer_valor_iva_factura', '_extraer_total_factura', '_extraer_base_factura', '_proveedor_candidato_valido', '_extraer_proveedor_factura', '_buscar_tercero_por_identificacion_carga', '_es_factura_duplicada_carga', '_validar_valores_factura_carga', '_estado_revision_carga', '_limpiar_monto_colombiano', '_extraer_montos_por_cuadrante_inferior', '_analizar_factura_carga', 'obtener_movimiento_compra_cxp', 'sincronizar_movimiento_compra_cxp', '_reporte_filtros', '_aplicar_filtros_movimientos', '_aplicar_filtros_cxp', '_calcular_resumen_reporte', '_datos_reportes_crv', '_periodo_texto', '_nombre_cuenta_valido', '_valor_movimiento_bancario', '_cuentas_financieras_crv', '_movimiento_es_bancario', '_impacto_movimiento_cuenta', '_excel_estilos_base', '_excel_titulo', '_excel_encabezado', '_excel_moneda', '_excel_auto_ancho', '_enviar_excel', '_pdf_estilos_crv', '_pdf_encabezado_historia', '_pdf_tabla', '_enviar_pdf', '_money_export', '_texto_pdf_seguro', '_clientes_crv', '_sincronizar_movimiento_cxc', '_nombre_proyecto_normalizado', '_movimientos_proyecto', '_cuentas_pagar_proyecto', '_cuentas_cobrar_proyecto', '_resumen_proyecto', '_clientes_proyectos_crv', '_rango_mes', '_cierre_periodo', '_periodo_crv_cerrado', '_movimientos_mes_crv', '_saldo_financiero_hasta', '_resumen_cierre_mes', '_fecha_formulario_cierre', 'bloquear_periodos_cerrados_crv', '_impacto_bancario_movimiento', '_saldo_cuenta_hasta', '_movimientos_cuenta_periodo', '_conciliacion_periodo']
