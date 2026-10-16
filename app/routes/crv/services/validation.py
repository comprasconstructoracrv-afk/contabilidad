"""CRV validation service helpers."""

from ..crv_context import (
    CRVMovimiento,
    CRVTercero,
    datetime,
    db,
    redirect,
    session,
    text,
)

def usuario_valido():
    return "usuario" in session

def empresa_crv_valida():
    """
    Este módulo es exclusivo de CRV Constructora.
    Evita mezclar datos con Hotel, Ecobike,
    Comercializadora o Financiera.
    """

    empresa_id = session.get("empresa_id")

    empresa_nombre = str(
        session.get("empresa_nombre", "")
    ).strip().upper()

    if not empresa_id:
        return False

    return (
        "CRV" in empresa_nombre
        and "CONSTRUCTORA" in empresa_nombre
    )

def proteger_crv():

    if not usuario_valido():
        return redirect("/login")

    if not session.get("empresa_id"):
        return redirect("/empresas")

    if not empresa_crv_valida():
        return redirect("/dashboard")

    return None

def convertir_fecha(valor):

    if not valor:
        return None

    try:
        return datetime.strptime(
            valor,
            "%Y-%m-%d"
        ).date()

    except ValueError:
        return None

def convertir_numero(valor, default=0):
    """
    Convierte valores monetarios sin multiplicarlos por 100.

    Acepta, entre otros:
      152100.84   -> 152100.84
      152100,84   -> 152100.84
      152.100,84  -> 152100.84
      152,100.84  -> 152100.84
      1.190.000   -> 1190000
      1,190,000   -> 1190000
      181000      -> 181000
    """

    if valor is None:
        return default

    texto = str(valor).strip()

    if not texto:
        return default

    texto = (
        texto
        .replace("$", "")
        .replace("COP", "")
        .replace("cop", "")
        .replace(" ", "")
        .strip()
    )

    if not texto:
        return default

    signo = ""

    if texto.startswith("-"):
        signo = "-"
        texto = texto[1:]
    elif texto.startswith("+"):
        texto = texto[1:]

    if not texto:
        return default

    tiene_punto = "." in texto
    tiene_coma = "," in texto

    try:
        if tiene_punto and tiene_coma:

            ultimo_punto = texto.rfind(".")
            ultima_coma = texto.rfind(",")

            if ultimo_punto > ultima_coma:
                texto = texto.replace(",", "")
            else:
                texto = texto.replace(".", "")
                texto = texto.replace(",", ".")

        elif tiene_coma:

            partes = texto.split(",")

            if (
                len(partes) == 2
                and len(partes[-1]) in (1, 2)
            ):
                texto = texto.replace(",", ".")
            else:
                texto = texto.replace(",", "")

        elif tiene_punto:

            partes = texto.split(".")

            if (
                len(partes) == 2
                and len(partes[-1]) in (1, 2)
            ):
                pass
            else:
                texto = texto.replace(".", "")

        return float(
            signo + texto
        )

    except (TypeError, ValueError):
        return default

def convertir_porcentaje(valor, default=0):

    if valor is None:
        return default

    texto = str(valor).strip().replace(",", ".")

    if not texto:
        return default

    try:
        return float(texto)
    except (TypeError, ValueError):
        return default

def calcular_iva_formulario(formulario):
    """
    Devuelve los valores tributarios del documento sin asumir que
    todo IVA pagado sea descontable.

    tipo_iva:
      - NO_APLICA
      - EXCLUIDO
      - EXENTO
      - GENERADO
      - DESCONTABLE
      - MAYOR_VALOR_COSTO

    EXENTO y EXCLUIDO siempre se guardan con tarifa 0 e IVA 0.
    """

    base_gravable = convertir_numero(
        formulario.get("base_gravable")
    )

    tipo_iva = str(
        formulario.get("tipo_iva", "NO_APLICA")
        or "NO_APLICA"
    ).strip().upper()

    tarifa_iva = convertir_porcentaje(
        formulario.get("tarifa_iva"),
        0
    )

    if tipo_iva in (
        "NO_APLICA",
        "EXCLUIDO",
        "EXENTO",
    ):
        tarifa_iva = 0
        valor_iva = 0
    else:
        tarifa_iva = max(0, tarifa_iva)
        valor_iva = round(
            base_gravable * tarifa_iva / 100,
            2
        )

    total_documento = round(
        base_gravable + valor_iva,
        2
    )

    return {
        "base_gravable": base_gravable,
        "tipo_iva": tipo_iva,
        "tarifa_iva": tarifa_iva,
        "valor_iva": valor_iva,
        "total_documento": total_documento,
    }

def resumen_iva_movimientos(movimientos):
    """
    Resumen tributario de IVA.

    IMPORTANTE:
    Los movimientos NO_APLICA siguen existiendo en contabilidad,
    pero NO se suman como base de IVA. Esto evita que nomina,
    transferencias, anticipos u otros conceptos sin IVA inflen la
    base tributaria del reporte.
    """

    resultado = {
        # Base gravable sujeta a IVA distinta de NO_APLICA,
        # EXENTO y EXCLUIDO.
        "base_gravable": 0.0,

        # Bases separadas por tratamiento.
        "base_generado": 0.0,
        "base_descontable": 0.0,
        "base_mayor_valor": 0.0,
        "base_exenta": 0.0,
        "base_excluida": 0.0,
        "base_no_aplica": 0.0,

        # Valores de impuesto.
        "iva_generado": 0.0,
        "iva_descontable": 0.0,
        "iva_mayor_valor": 0.0,
        "iva_total": 0.0,

        # Referencia gerencial. No sustituye la liquidacion fiscal
        # definitiva del contador.
        "saldo_iva_preliminar": 0.0,
    }

    for movimiento in movimientos:
        base = float(
            getattr(movimiento, "base_gravable", 0)
            or 0
        )

        iva = float(
            getattr(movimiento, "valor_iva", 0)
            or 0
        )

        tipo = str(
            getattr(movimiento, "tipo_iva", "NO_APLICA")
            or "NO_APLICA"
        ).strip().upper()

        if tipo == "GENERADO":
            resultado["base_gravable"] += base
            resultado["base_generado"] += base
            resultado["iva_generado"] += iva
            resultado["iva_total"] += iva

        elif tipo == "DESCONTABLE":
            resultado["base_gravable"] += base
            resultado["base_descontable"] += base
            resultado["iva_descontable"] += iva
            resultado["iva_total"] += iva

        elif tipo == "MAYOR_VALOR_COSTO":
            resultado["base_gravable"] += base
            resultado["base_mayor_valor"] += base
            resultado["iva_mayor_valor"] += iva
            resultado["iva_total"] += iva

        elif tipo == "EXENTO":
            resultado["base_exenta"] += base

        elif tipo == "EXCLUIDO":
            resultado["base_excluida"] += base

        else:
            # NO_APLICA y cualquier registro historico no tributario.
            resultado["base_no_aplica"] += base

    resultado["saldo_iva_preliminar"] = (
        resultado["iva_generado"]
        - resultado["iva_descontable"]
    )

    return resultado

def obtener_tercero_por_identificacion(
    empresa_id,
    identificacion
):

    identificacion = str(
        identificacion or ""
    ).strip()

    if not identificacion:
        return None

    return CRVTercero.query.filter_by(
        empresa_id=empresa_id,
        identificacion=identificacion
    ).first()

def crear_o_actualizar_tercero_desde_formulario(
    empresa_id,
    formulario
):

    identificacion = formulario.get(
        "tercero_identificacion",
        ""
    ).strip()

    razon_social = formulario.get(
        "tercero_nombre",
        ""
    ).strip()

    if not identificacion and not razon_social:
        return None

    tercero = None

    if identificacion:

        tercero = obtener_tercero_por_identificacion(
            empresa_id,
            identificacion
        )

    if tercero is None:

        tercero = CRVTercero(
            empresa_id=empresa_id,

            tipo_tercero=formulario.get(
                "tipo_tercero",
                "TERCERO"
            ).strip().upper() or "TERCERO",

            tipo_documento=formulario.get(
                "tipo_documento_tercero",
                ""
            ).strip(),

            identificacion=(
                identificacion
                or f"SIN-DOC-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            ),

            razon_social=(
                razon_social
                or "TERCERO SIN NOMBRE"
            ),

            nombre_comercial=formulario.get(
                "tercero_nombre_comercial",
                ""
            ).strip(),

            direccion=formulario.get(
                "tercero_direccion",
                ""
            ).strip(),

            ciudad=formulario.get(
                "tercero_ciudad",
                ""
            ).strip(),

            departamento=formulario.get(
                "tercero_departamento",
                ""
            ).strip(),

            telefono=formulario.get(
                "tercero_telefono",
                ""
            ).strip(),

            celular=formulario.get(
                "tercero_celular",
                ""
            ).strip(),

            email=formulario.get(
                "tercero_email",
                ""
            ).strip(),

            contacto=formulario.get(
                "tercero_contacto",
                ""
            ).strip()
        )

        db.session.add(tercero)
        db.session.flush()

    else:

        if razon_social:
            tercero.razon_social = razon_social

        tipo_tercero = formulario.get(
            "tipo_tercero",
            ""
        ).strip()

        if tipo_tercero:
            tercero.tipo_tercero = tipo_tercero.upper()

        campos = {
            "nombre_comercial": "tercero_nombre_comercial",
            "direccion": "tercero_direccion",
            "ciudad": "tercero_ciudad",
            "departamento": "tercero_departamento",
            "telefono": "tercero_telefono",
            "celular": "tercero_celular",
            "email": "tercero_email",
            "contacto": "tercero_contacto"
        }

        for atributo, campo_form in campos.items():

            valor = formulario.get(
                campo_form,
                ""
            ).strip()

            if valor:
                setattr(
                    tercero,
                    atributo,
                    valor
                )

    return tercero

def _tipo_comprobante_movimiento(movimiento):
    """
    Determina el tipo de comprobante interno.

    RC = Recibo de caja:
         entrada real de dinero.

    CE = Comprobante de egreso:
         salida real de dinero.

    CC = Comprobante contable:
         reconocimiento contable sin entrada/salida inmediata,
         saldos iniciales, transferencias internas y operaciones
         a credito.
    """

    tipo = str(
        movimiento.tipo or ""
    ).strip().upper()

    forma_pago = str(
        movimiento.forma_pago or ""
    ).strip().upper()

    cuenta = str(
        movimiento.cuenta or ""
    ).strip().upper()

    if tipo == "COBRO CUENTA POR COBRAR":
        return "RECIBO DE CAJA", "RC"

    if tipo == "INGRESO":
        if (
            forma_pago in ("CREDITO", "CRÉDITO")
            or cuenta == "CUENTAS POR COBRAR"
        ):
            return "COMPROBANTE CONTABLE", "CC"

        return "RECIBO DE CAJA", "RC"

    if tipo == "COMPRA":
        if (
            forma_pago in ("CREDITO", "CRÉDITO")
            or cuenta == "CUENTAS POR PAGAR"
        ):
            return "COMPROBANTE CONTABLE", "CC"

        return "COMPROBANTE DE EGRESO", "CE"

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

    if tipo in tipos_egreso:
        return "COMPROBANTE DE EGRESO", "CE"

    return "COMPROBANTE CONTABLE", "CC"

def _titulo_comprobante_por_prefijo(prefijo):
    prefijo = str(
        prefijo or ""
    ).strip().upper()

    if prefijo == "RC":
        return "RECIBO DE CAJA"

    if prefijo == "CE":
        return "COMPROBANTE DE EGRESO"

    return "COMPROBANTE CONTABLE"

def _asegurar_tabla_secuencias_comprobantes():
    """
    Conserva el ultimo numero utilizado por empresa y por serie.
    Esta tabla impide reutilizar un consecutivo aunque posteriormente
    se elimine el movimiento que lo utilizo.
    """

    db.session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS crv_comprobante_secuencia (
                empresa_id INTEGER NOT NULL,
                comprobante_tipo VARCHAR(10) NOT NULL,
                ultimo_consecutivo INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (empresa_id, comprobante_tipo)
            )
            """
        )
    )

def _siguiente_consecutivo_comprobante(
    empresa_id,
    comprobante_tipo
):
    """
    Obtiene el siguiente numero de la serie CE / RC / CC.

    Si la tabla de secuencias aun no tiene registro para una serie,
    toma como punto de partida el mayor consecutivo historico ya
    asignado en crv_movimiento.
    """

    empresa_id = int(empresa_id)
    comprobante_tipo = str(
        comprobante_tipo or "CC"
    ).strip().upper()

    _asegurar_tabla_secuencias_comprobantes()

    fila = db.session.execute(
        text(
            """
            SELECT ultimo_consecutivo
            FROM crv_comprobante_secuencia
            WHERE
                empresa_id = :empresa_id
                AND comprobante_tipo = :tipo
            """
        ),
        {
            "empresa_id": empresa_id,
            "tipo": comprobante_tipo,
        }
    ).mappings().first()

    if fila is None:
        maximo_historico = db.session.query(
            db.func.max(
                CRVMovimiento.comprobante_consecutivo
            )
        ).filter(
            CRVMovimiento.empresa_id == empresa_id,
            CRVMovimiento.comprobante_tipo == comprobante_tipo
        ).scalar()

        ultimo = int(
            maximo_historico
            or 0
        )

        db.session.execute(
            text(
                """
                INSERT INTO crv_comprobante_secuencia (
                    empresa_id,
                    comprobante_tipo,
                    ultimo_consecutivo
                )
                VALUES (
                    :empresa_id,
                    :tipo,
                    :ultimo
                )
                """
            ),
            {
                "empresa_id": empresa_id,
                "tipo": comprobante_tipo,
                "ultimo": ultimo,
            }
        )
    else:
        ultimo = int(
            fila["ultimo_consecutivo"]
            or 0
        )

    siguiente = ultimo + 1

    db.session.execute(
        text(
            """
            UPDATE crv_comprobante_secuencia
            SET ultimo_consecutivo = :siguiente
            WHERE
                empresa_id = :empresa_id
                AND comprobante_tipo = :tipo
            """
        ),
        {
            "siguiente": siguiente,
            "empresa_id": empresa_id,
            "tipo": comprobante_tipo,
        }
    )

    return siguiente

def _asignar_comprobante_permanente(movimiento):
    """
    Asigna el comprobante una sola vez.

    Si el movimiento ya tiene tipo, consecutivo y codigo, no se
    modifica. De esta forma editar el movimiento o volver a abrir
    el PDF no cambia el numero emitido.
    """

    if movimiento is None:
        return None

    tipo_guardado = str(
        getattr(
            movimiento,
            "comprobante_tipo",
            ""
        )
        or ""
    ).strip().upper()

    consecutivo_guardado = int(
        getattr(
            movimiento,
            "comprobante_consecutivo",
            0
        )
        or 0
    )

    codigo_guardado = str(
        getattr(
            movimiento,
            "comprobante_codigo",
            ""
        )
        or ""
    ).strip().upper()

    if (
        tipo_guardado
        and consecutivo_guardado > 0
        and codigo_guardado
    ):
        return codigo_guardado

    # Si la migracion dejo tipo + numero pero falta solamente el
    # codigo visible, se reconstruye sin consumir un numero nuevo.
    if (
        tipo_guardado
        and consecutivo_guardado > 0
    ):
        codigo = (
            f"{tipo_guardado}-"
            f"{consecutivo_guardado:06d}"
        )

        movimiento.comprobante_codigo = codigo

        return codigo

    _, prefijo = _tipo_comprobante_movimiento(
        movimiento
    )

    siguiente = _siguiente_consecutivo_comprobante(
        movimiento.empresa_id,
        prefijo
    )

    codigo = (
        f"{prefijo}-"
        f"{siguiente:06d}"
    )

    movimiento.comprobante_tipo = prefijo
    movimiento.comprobante_consecutivo = siguiente
    movimiento.comprobante_codigo = codigo

    return codigo

__all__ = ['_asegurar_tabla_secuencias_comprobantes', '_asignar_comprobante_permanente', '_siguiente_consecutivo_comprobante', '_tipo_comprobante_movimiento', '_titulo_comprobante_por_prefijo', 'calcular_iva_formulario', 'convertir_fecha', 'convertir_numero', 'convertir_porcentaje', 'crear_o_actualizar_tercero_desde_formulario', 'empresa_crv_valida', 'obtener_tercero_por_identificacion', 'proteger_crv', 'resumen_iva_movimientos', 'usuario_valido']
