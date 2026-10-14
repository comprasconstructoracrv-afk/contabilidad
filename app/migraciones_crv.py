from sqlalchemy import inspect, text

from app.extensions import db


# ============================================================
# MIGRACIÓN SEGURA CRV
# - NO elimina tablas
# - NO elimina registros
# - NO renombra columnas existentes
# - Solo agrega columnas que falten
# ============================================================


SCHEMA_CRV = {
    "crv_movimiento": {
        "empresa_id": "INTEGER",
        "sede_id": "INTEGER",
        "fecha": "DATE",
        "tipo": "VARCHAR(80)",
        "categoria": "VARCHAR(120)",
        "subcategoria": "VARCHAR(120)",
        "concepto": "VARCHAR(300)",
        "descripcion": "TEXT",
        "tercero_id": "INTEGER",
        "tercero_nombre": "VARCHAR(220)",
        "tercero_identificacion": "VARCHAR(80)",
        "tercero_direccion": "VARCHAR(250)",
        "tercero_email": "VARCHAR(180)",
        "tercero_telefono": "VARCHAR(80)",
        "tercero_contacto": "VARCHAR(180)",
        "tipo_documento": "VARCHAR(80)",
        "numero_documento": "VARCHAR(120)",
        "numero_soporte": "VARCHAR(120)",
        "fecha_documento": "DATE",
        "fecha_vencimiento": "DATE",

        # IVA
        "base_gravable": "FLOAT NOT NULL DEFAULT 0",
        "tipo_iva": "VARCHAR(30) NOT NULL DEFAULT 'NO_APLICA'",
        "tarifa_iva": "FLOAT NOT NULL DEFAULT 0",
        "valor_iva": "FLOAT NOT NULL DEFAULT 0",

        # Valores
        "valor": "FLOAT NOT NULL DEFAULT 0",
        "descuento": "FLOAT NOT NULL DEFAULT 0",
        "retencion": "FLOAT NOT NULL DEFAULT 0",
        "otros_descuentos": "FLOAT NOT NULL DEFAULT 0",
        "valor_neto": "FLOAT NOT NULL DEFAULT 0",

        # Pago / banco
        "forma_pago": "VARCHAR(80)",
        "cuenta": "VARCHAR(150)",
        "cuenta_destino": "VARCHAR(180)",
        "beneficiario": "VARCHAR(180)",
        "referencia_pago": "VARCHAR(120)",

        # Clasificación
        "proyecto": "VARCHAR(150)",
        "centro_costo": "VARCHAR(150)",
        "obra": "VARCHAR(150)",

        # Control
        "observaciones": "TEXT",
        "revisado": "BOOLEAN NOT NULL DEFAULT 0",
        "estado": "VARCHAR(30) NOT NULL DEFAULT 'ACTIVO'",
        "origen_registro": "VARCHAR(100) NOT NULL DEFAULT 'SISTEMA'",
        "usuario_registro": "VARCHAR(120)",

        # Comprobante individual permanente
        # CE = Comprobante de egreso
        # RC = Recibo de caja
        # CC = Comprobante contable
        "comprobante_tipo": "VARCHAR(10)",
        "comprobante_consecutivo": "INTEGER",
        "comprobante_codigo": "VARCHAR(30)",

        "fecha_creacion": "DATETIME",
        "fecha_actualizacion": "DATETIME",
    },

    "crv_cuenta_pagar": {
        "empresa_id": "INTEGER",
        "proveedor_id": "INTEGER",
        "sede_id": "INTEGER",
        "tipo_documento": "VARCHAR(60)",
        "numero_documento": "VARCHAR(120)",
        "fecha_documento": "DATE",
        "fecha_vencimiento": "DATE",
        "concepto": "VARCHAR(300)",
        "descripcion": "TEXT",

        # IVA
        "base_gravable": "FLOAT NOT NULL DEFAULT 0",
        "tipo_iva": "VARCHAR(30) NOT NULL DEFAULT 'NO_APLICA'",
        "tarifa_iva": "FLOAT NOT NULL DEFAULT 0",
        "valor_iva": "FLOAT NOT NULL DEFAULT 0",

        # Valores
        "valor_bruto": "FLOAT NOT NULL DEFAULT 0",
        "descuento": "FLOAT NOT NULL DEFAULT 0",
        "retencion": "FLOAT NOT NULL DEFAULT 0",
        "otros_descuentos": "FLOAT NOT NULL DEFAULT 0",
        "valor_neto": "FLOAT NOT NULL DEFAULT 0",
        "total_pagado": "FLOAT NOT NULL DEFAULT 0",
        "saldo_pendiente": "FLOAT NOT NULL DEFAULT 0",

        # Clasificación
        "categoria": "VARCHAR(120)",
        "subcategoria": "VARCHAR(120)",
        "proyecto": "VARCHAR(150)",
        "centro_costo": "VARCHAR(150)",
        "obra": "VARCHAR(150)",

        # Control
        "estado": "VARCHAR(30) NOT NULL DEFAULT 'PENDIENTE'",
        "observaciones": "TEXT",
        "origen_registro": "VARCHAR(80) NOT NULL DEFAULT 'SISTEMA'",
        "usuario_registro": "VARCHAR(120)",
        "fecha_creacion": "DATETIME",
        "fecha_actualizacion": "DATETIME",
    },

    "crv_cuenta_cobrar": {
        "empresa_id": "INTEGER",
        "cliente_id": "INTEGER",
        "sede_id": "INTEGER",
        "tipo_documento": "VARCHAR(60)",
        "numero_documento": "VARCHAR(120)",
        "fecha_documento": "DATE",
        "fecha_vencimiento": "DATE",
        "concepto": "VARCHAR(300)",
        "descripcion": "TEXT",

        # IVA
        "base_gravable": "FLOAT NOT NULL DEFAULT 0",
        "tipo_iva": "VARCHAR(30) NOT NULL DEFAULT 'NO_APLICA'",
        "tarifa_iva": "FLOAT NOT NULL DEFAULT 0",
        "valor_iva": "FLOAT NOT NULL DEFAULT 0",

        # Valores
        "valor_bruto": "FLOAT NOT NULL DEFAULT 0",
        "descuento": "FLOAT NOT NULL DEFAULT 0",
        "retencion": "FLOAT NOT NULL DEFAULT 0",
        "otros_descuentos": "FLOAT NOT NULL DEFAULT 0",
        "valor_neto": "FLOAT NOT NULL DEFAULT 0",
        "total_cobrado": "FLOAT NOT NULL DEFAULT 0",
        "saldo_pendiente": "FLOAT NOT NULL DEFAULT 0",

        # Clasificación
        "categoria": "VARCHAR(120)",
        "subcategoria": "VARCHAR(120)",
        "proyecto": "VARCHAR(150)",
        "centro_costo": "VARCHAR(150)",
        "obra": "VARCHAR(150)",

        # Control
        "estado": "VARCHAR(30) NOT NULL DEFAULT 'PENDIENTE'",
        "observaciones": "TEXT",
        "origen_registro": "VARCHAR(80) NOT NULL DEFAULT 'SISTEMA'",
        "usuario_registro": "VARCHAR(120)",
        "fecha_creacion": "DATETIME",
        "fecha_actualizacion": "DATETIME",
    },
}


def _tabla_existe(tabla):
    inspector = inspect(db.engine)
    return tabla in inspector.get_table_names()


def _columnas_existentes(tabla):
    inspector = inspect(db.engine)

    return {
        columna["name"]
        for columna in inspector.get_columns(tabla)
    }


def _agregar_columnas_faltantes(tabla):
    if not _tabla_existe(tabla):
        return

    existentes = _columnas_existentes(tabla)

    with db.engine.begin() as conexion:
        for nombre, definicion in SCHEMA_CRV[tabla].items():
            if nombre in existentes:
                continue

            conexion.execute(
                text(
                    f'ALTER TABLE "{tabla}" '
                    f'ADD COLUMN "{nombre}" {definicion}'
                )
            )


def _normalizar_movimientos_historicos():
    if not _tabla_existe("crv_movimiento"):
        return

    columnas = _columnas_existentes(
        "crv_movimiento"
    )

    with db.engine.begin() as conexion:

        # Fechas de auditoría para registros anteriores.
        if (
            "fecha_creacion" in columnas
            and "fecha_actualizacion" in columnas
        ):
            conexion.execute(
                text(
                    """
                    UPDATE crv_movimiento
                    SET
                        fecha_creacion = COALESCE(
                            fecha_creacion,
                            CURRENT_TIMESTAMP
                        ),
                        fecha_actualizacion = COALESCE(
                            fecha_actualizacion,
                            CURRENT_TIMESTAMP
                        )
                    """
                )
            )

        # IVA histórico: NO altera valor, neto ni saldos anteriores.
        if {
            "base_gravable",
            "tipo_iva",
            "tarifa_iva",
            "valor_iva",
            "valor"
        }.issubset(columnas):

            conexion.execute(
                text(
                    """
                    UPDATE crv_movimiento
                    SET
                        base_gravable = CASE
                            WHEN COALESCE(base_gravable, 0) = 0
                            THEN COALESCE(valor, 0)
                            ELSE base_gravable
                        END,
                        tipo_iva = COALESCE(
                            NULLIF(tipo_iva, ''),
                            'NO_APLICA'
                        ),
                        tarifa_iva = COALESCE(tarifa_iva, 0),
                        valor_iva = COALESCE(valor_iva, 0)
                    WHERE
                        COALESCE(valor_iva, 0) = 0
                    """
                )
            )


def _normalizar_cuentas_pagar_historicas():
    if not _tabla_existe("crv_cuenta_pagar"):
        return

    columnas = _columnas_existentes(
        "crv_cuenta_pagar"
    )

    with db.engine.begin() as conexion:

        if (
            "fecha_creacion" in columnas
            and "fecha_actualizacion" in columnas
        ):
            conexion.execute(
                text(
                    """
                    UPDATE crv_cuenta_pagar
                    SET
                        fecha_creacion = COALESCE(
                            fecha_creacion,
                            CURRENT_TIMESTAMP
                        ),
                        fecha_actualizacion = COALESCE(
                            fecha_actualizacion,
                            CURRENT_TIMESTAMP
                        )
                    """
                )
            )

        if {
            "base_gravable",
            "tipo_iva",
            "tarifa_iva",
            "valor_iva",
            "valor_bruto"
        }.issubset(columnas):

            conexion.execute(
                text(
                    """
                    UPDATE crv_cuenta_pagar
                    SET
                        base_gravable = CASE
                            WHEN COALESCE(base_gravable, 0) = 0
                            THEN COALESCE(valor_bruto, 0)
                            ELSE base_gravable
                        END,
                        tipo_iva = COALESCE(
                            NULLIF(tipo_iva, ''),
                            'NO_APLICA'
                        ),
                        tarifa_iva = COALESCE(tarifa_iva, 0),
                        valor_iva = COALESCE(valor_iva, 0)
                    WHERE
                        COALESCE(valor_iva, 0) = 0
                    """
                )
            )


def _normalizar_cuentas_cobrar_historicas():
    if not _tabla_existe("crv_cuenta_cobrar"):
        return

    columnas = _columnas_existentes(
        "crv_cuenta_cobrar"
    )

    with db.engine.begin() as conexion:

        if (
            "fecha_creacion" in columnas
            and "fecha_actualizacion" in columnas
        ):
            conexion.execute(
                text(
                    """
                    UPDATE crv_cuenta_cobrar
                    SET
                        fecha_creacion = COALESCE(
                            fecha_creacion,
                            CURRENT_TIMESTAMP
                        ),
                        fecha_actualizacion = COALESCE(
                            fecha_actualizacion,
                            CURRENT_TIMESTAMP
                        )
                    """
                )
            )

        if {
            "base_gravable",
            "tipo_iva",
            "tarifa_iva",
            "valor_iva",
            "valor_bruto"
        }.issubset(columnas):

            conexion.execute(
                text(
                    """
                    UPDATE crv_cuenta_cobrar
                    SET
                        base_gravable = CASE
                            WHEN COALESCE(base_gravable, 0) = 0
                            THEN COALESCE(valor_bruto, 0)
                            ELSE base_gravable
                        END,
                        tipo_iva = COALESCE(
                            NULLIF(tipo_iva, ''),
                            'NO_APLICA'
                        ),
                        tarifa_iva = COALESCE(tarifa_iva, 0),
                        valor_iva = COALESCE(valor_iva, 0)
                    WHERE
                        COALESCE(valor_iva, 0) = 0
                    """
                )
            )



def _tipo_comprobante_historico(tipo, forma_pago):
    """
    Clasifica movimientos históricos para asignarles una serie
    permanente de comprobante.

    RC = Recibo de caja
    CE = Comprobante de egreso
    CC = Comprobante contable
    """

    tipo = str(tipo or "").strip().upper()
    forma_pago = str(forma_pago or "").strip().upper()

    tipos_ingreso = {
        "INGRESO",
        "COBRO CUENTA POR COBRAR",
    }

    tipos_egreso = {
        "GASTO",
        "NOMINA AFILIADOS",
        "NÓMINA AFILIADOS",
        "NOMINA OBRA",
        "NÓMINA OBRA",
        "ANTICIPO",
        "PRESTAMO EMPLEADO",
        "PRÉSTAMO EMPLEADO",
        "EGRESO",
        "OTRO EGRESO",
        "PAGO CUENTA POR PAGAR",
    }

    if tipo in tipos_ingreso:
        return "RC"

    if tipo == "COMPRA":
        if forma_pago in ("CREDITO", "CRÉDITO"):
            return "CC"
        return "CE"

    if tipo in tipos_egreso:
        return "CE"

    return "CC"


def _normalizar_comprobantes_historicos():
    """
    Asigna una sola vez consecutivos permanentes a movimientos que
    todavía no los tengan.

    - No modifica consecutivos ya asignados.
    - Mantiene series independientes CE, RC y CC.
    - Mantiene series independientes por empresa.
    - Puede ejecutarse nuevamente sin renumerar.
    """

    if not _tabla_existe("crv_movimiento"):
        return

    columnas = _columnas_existentes("crv_movimiento")

    necesarias = {
        "id",
        "empresa_id",
        "tipo",
        "forma_pago",
        "comprobante_tipo",
        "comprobante_consecutivo",
        "comprobante_codigo",
    }

    if not necesarias.issubset(columnas):
        return

    with db.engine.begin() as conexion:
        maximos = {}

        filas_maximos = conexion.execute(
            text(
                """
                SELECT
                    empresa_id,
                    comprobante_tipo,
                    MAX(comprobante_consecutivo) AS ultimo
                FROM crv_movimiento
                WHERE
                    comprobante_tipo IS NOT NULL
                    AND comprobante_tipo <> ''
                    AND comprobante_consecutivo IS NOT NULL
                GROUP BY
                    empresa_id,
                    comprobante_tipo
                """
            )
        ).mappings().all()

        for fila in filas_maximos:
            clave = (
                fila["empresa_id"],
                fila["comprobante_tipo"],
            )
            maximos[clave] = int(fila["ultimo"] or 0)

        pendientes = conexion.execute(
            text(
                """
                SELECT
                    id,
                    empresa_id,
                    tipo,
                    forma_pago
                FROM crv_movimiento
                WHERE
                    comprobante_consecutivo IS NULL
                    OR comprobante_consecutivo = 0
                    OR comprobante_tipo IS NULL
                    OR comprobante_tipo = ''
                    OR comprobante_codigo IS NULL
                    OR comprobante_codigo = ''
                ORDER BY
                    empresa_id ASC,
                    fecha ASC,
                    id ASC
                """
            )
        ).mappings().all()

        for fila in pendientes:
            empresa_id = fila["empresa_id"]

            tipo_comprobante = _tipo_comprobante_historico(
                fila["tipo"],
                fila["forma_pago"]
            )

            clave = (
                empresa_id,
                tipo_comprobante,
            )

            siguiente = maximos.get(clave, 0) + 1

            codigo = (
                f"{tipo_comprobante}-"
                f"{siguiente:06d}"
            )

            conexion.execute(
                text(
                    """
                    UPDATE crv_movimiento
                    SET
                        comprobante_tipo = :tipo,
                        comprobante_consecutivo = :consecutivo,
                        comprobante_codigo = :codigo
                    WHERE id = :id
                    """
                ),
                {
                    "tipo": tipo_comprobante,
                    "consecutivo": siguiente,
                    "codigo": codigo,
                    "id": fila["id"],
                }
            )

            maximos[clave] = siguiente


def _crear_indice_comprobantes():
    """
    Evita repetir un mismo consecutivo dentro de la misma empresa
    y de la misma serie CE / RC / CC.
    """

    if not _tabla_existe("crv_movimiento"):
        return

    columnas = _columnas_existentes("crv_movimiento")

    necesarias = {
        "empresa_id",
        "comprobante_tipo",
        "comprobante_consecutivo",
    }

    if not necesarias.issubset(columnas):
        return

    with db.engine.begin() as conexion:
        conexion.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS
                ux_crv_movimiento_comprobante
                ON crv_movimiento (
                    empresa_id,
                    comprobante_tipo,
                    comprobante_consecutivo
                )
                """
            )
        )


def migrar_iva_crv():
    """
    Sincroniza de forma NO DESTRUCTIVA las tablas CRV actuales.

    IMPORTANTE:
    - No elimina tablas.
    - No elimina movimientos.
    - No elimina CxP ni CxC.
    - No reemplaza valores contables existentes.
    - Solo agrega columnas faltantes.
    - Completa campos nuevos para registros históricos.
    - Agrega y conserva consecutivos permanentes CE / RC / CC.
    - No renumera comprobantes previamente asignados.
    """

    for tabla in SCHEMA_CRV:
        _agregar_columnas_faltantes(
            tabla
        )

    _normalizar_movimientos_historicos()
    _normalizar_cuentas_pagar_historicas()
    _normalizar_cuentas_cobrar_historicas()

    # Consecutivos permanentes de comprobantes CE / RC / CC.
    # No renumera registros que ya tengan consecutivo.
    _normalizar_comprobantes_historicos()
    _crear_indice_comprobantes()
