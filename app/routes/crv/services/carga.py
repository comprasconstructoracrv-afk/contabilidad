"""CRV carga service helpers."""

from ..crv_context import (
    CRVCuentaPagar,
    CRVMovimiento,
    CRVTercero,
    Path,
    PdfReader,
    current_app,
    datetime,
    db,
    json,
    re,
    session,
)
from math import isfinite
from .validation import (
    convertir_numero,
)
from .cuentas_pagar import sincronizar_movimiento_compra_cxp

EXTENSIONES_CARGA_INTELIGENTE = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
TAMANO_MAXIMO_ARCHIVO_CARGA = 25 * 1024 * 1024

def _carpeta_carga_inteligente(empresa_id):
    carpeta = (
        Path(current_app.instance_path)
        / "crv_carga_inteligente"
        / str(int(empresa_id))
    )

    carpeta.mkdir(
        parents=True,
        exist_ok=True
    )

    return carpeta

def _ruta_lote_carga(empresa_id, lote_id):
    lote_seguro = str(
        lote_id or ""
    ).strip()

    if not lote_seguro:
        return None

    permitidos = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789-_"
    )

    if any(
        caracter not in permitidos
        for caracter in lote_seguro
    ):
        return None

    return (
        _carpeta_carga_inteligente(
            empresa_id
        )
        / lote_seguro
    )

def _leer_manifest_carga(empresa_id, lote_id):
    carpeta = _ruta_lote_carga(
        empresa_id,
        lote_id
    )

    if not carpeta:
        return None

    ruta = carpeta / "lote.json"

    if not ruta.exists():
        return None

    try:
        return json.loads(
            ruta.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return None

def _guardar_manifest_carga(
    empresa_id,
    lote_id,
    datos
):
    carpeta = _ruta_lote_carga(
        empresa_id,
        lote_id
    )

    if not carpeta:
        raise ValueError(
            "Identificador de lote no valido."
        )

    carpeta.mkdir(
        parents=True,
        exist_ok=True
    )

    ruta = carpeta / "lote.json"

    ruta.write_text(
        json.dumps(
            datos,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

def _listar_lotes_carga_inteligente(
    empresa_id,
    limite=20
):
    raiz = _carpeta_carga_inteligente(
        empresa_id
    )

    lotes = []

    for carpeta in raiz.iterdir():

        if not carpeta.is_dir():
            continue

        manifest = _leer_manifest_carga(
            empresa_id,
            carpeta.name
        )

        if not manifest:
            continue

        lotes.append(
            manifest
        )

    lotes.sort(
        key=lambda x: str(
            x.get(
                "fecha_creacion",
                ""
            )
        ),
        reverse=True
    )

    return lotes[:limite]

def _archivo_carga_valido(archivo):
    if archivo is None:
        return False, "Archivo invalido."

    nombre_original = str(
        archivo.filename or ""
    ).strip()

    if not nombre_original:
        return False, "El archivo no tiene nombre."

    extension = Path(
        nombre_original
    ).suffix.lower()

    if extension not in EXTENSIONES_CARGA_INTELIGENTE:
        return (
            False,
            (
                "Formato no permitido. "
                "Usa PDF, PNG, JPG, JPEG o WEBP."
            )
        )

    return True, ""

def _normalizar_identificacion_carga(valor):
    return re.sub(
        r"[^0-9A-Za-z]",
        "",
        str(valor or "")
    ).upper()

def _limpiar_texto_factura(texto):
    lineas = []

    for linea in str(
        texto or ""
    ).replace(
        "\r",
        "\n"
    ).split(
        "\n"
    ):
        limpia = re.sub(
            r"\s+",
            " ",
            linea
        ).strip()

        if limpia:
            lineas.append(
                limpia
            )

    return "\n".join(
        lineas
    )

def _leer_texto_pdf(ruta):
    if PdfReader is None:
        return "", (
            "Falta instalar pypdf. "
            "Ejecuta: py -m pip install pypdf"
        )

    try:
        lector = PdfReader(
            str(ruta)
        )

        paginas = []

        for pagina in lector.pages:
            try:
                paginas.append(
                    pagina.extract_text()
                    or ""
                )
            except Exception:
                paginas.append(
                    ""
                )

        texto = _limpiar_texto_factura(
            "\n".join(
                paginas
            )
        )

        if not texto:
            return "", (
                "El PDF no contiene texto seleccionable. "
                "Quedará para revisión manual."
            )

        return texto, ""

    except Exception as error:
        return "", (
            "No fue posible leer el PDF: "
            f"{error}"
        )

def _encontrar_valor_despues_etiqueta(
    texto,
    etiquetas
):
    for etiqueta in etiquetas:
        patron = (
            rf"(?im)"
            rf"{etiqueta}"
            rf"[^\n0-9]{{0,20}}"
            rf"(\$?\s*[0-9][0-9\.,]*)"
        )

        coincidencia = re.search(
            patron,
            texto
        )

        if coincidencia:
            return convertir_numero(
                coincidencia.group(1),
                None
            )

    return None

def _extraer_fecha_factura(texto, nombre_archivo=""):
    patrones_prioritarios = [
        r"(?im)\bFECHA\s+(?:DE\s+)?(?:EMISI[ÓO]N|EXPEDICI[ÓO]N|FACTURA|DOCUMENTO)\s*[:#-]?\s*(\d{2}[-/.]\d{2}[-/.]\d{2,4}|\d{4}[-/.]\d{2}[-/.]\d{2}|\d{2}-[A-Za-z]{3}-\d{4})",
        r"(?im)\bFECHA\s*[:#-]\s*(\d{2}[-/.]\d{2}[-/.]\d{2,4}|\d{4}[-/.]\d{2}[-/.]\d{2}|\d{2}-[A-Za-z]{3}-\d{4})",
    ]
    patrones_generales = [
        r"(?<!\d)(\d{2}[-/]\d{2}[-/]\d{4})(?!\d)",
        r"(?<!\d)(\d{2}\.\d{2}\.\d{4})(?!\d)",
        r"(?<!\d)(\d{2}[-/]\d{2}[-/]\d{2})(?!\d)",
        r"(?<!\d)(\d{4}[-/]\d{2}[-/]\d{2})(?!\d)",
        r"(?<!\d)(\d{2}-[A-Za-z]{3}-\d{4})(?!\d)",
    ]

    candidatos = []
    for patron in patrones_prioritarios:
        candidatos.extend(re.findall(patron, str(texto or "")))
    if not candidatos:
        for fuente in (texto, nombre_archivo):
            for patron in patrones_generales:
                candidatos.extend(re.findall(patron, str(fuente or "")))

    for candidato in candidatos:
        for formato in (
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%d.%m.%Y",
            "%d-%m-%y",
            "%d/%m/%y",
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%d-%b-%Y",
        ):
            try:
                return datetime.strptime(
                    candidato,
                    formato
                ).date().isoformat()
            except Exception:
                continue

    return ""

def _extraer_nit_factura(texto):
    patrones = [
        r"(?im)\b(?:N\.?\s*I\.?\s*T\.?|NIT)\s*[:#-]?\s*([0-9][0-9.\-\t ]{4,24})",
        r"(?im)\b(?:C\.?\s*C\.?|C[ÉE]DULA(?:\s+DE\s+CIUDADAN[ÍI]A)?|IDENTIFICACI[ÓO]N)\s*[:#-]?\s*([0-9][0-9.\-\t ]{4,24})",
    ]

    for patron in patrones:
        coincidencia = re.search(
            patron,
            texto
        )

        if coincidencia:
            return coincidencia.group(1).strip(" .-\t")

    return ""

def _tipo_documento_factura(texto):
    if re.search(r"(?i)\b(?:N\.?\s*I\.?\s*T\.?|NIT)\b", texto):
        return "NIT"
    if re.search(
        r"(?i)\b(?:C\.?\s*C\.?|C[ÉE]DULA|IDENTIFICACI[ÓO]N)\b",
        texto,
    ):
        return "CEDULA"
    return ""

def _numero_factura_candidato_valido(valor):
    candidato = str(valor or "").strip().upper()

    if not candidato or len(candidato) < 3:
        return False

    prohibidos = {
        "EMAIL", "E-MAIL", "MAIL", "MEDIO", "REMISION", "REMISIÓN",
        "PAGO", "VENTA", "FECHA", "TOTAL", "FACTURA", "DOCUMENTO",
        "CLIENTE", "ADQUIRENTE", "CONTADO", "CREDITO", "CRÉDITO",
    }

    if candidato in prohibidos:
        return False

    if any(palabra in candidato for palabra in ("EMAIL", "REMISION", "REMISIÓN")):
        return False

    # Un número de factura normalmente contiene al menos un dígito.
    if not re.search(r"\d", candidato):
        return False

    return True

def _extraer_numero_factura(texto):
    patrones = [
        r"(?im)FACTURA\s+ELECTR[ÓO]NICA(?:\s+DE\s+VENTA)?\s*(?:No\.?|N[°º])?\s*[:#-]?\s*([A-Z0-9][A-Z0-9\-]{2,29})",
        r"(?im)\bFACTURA\s*(?:No\.?|N[°º])\s*[:#-]?\s*([A-Z0-9][A-Z0-9\-]{2,29})",
        r"(?im)\b(?:No\.?|N[°º])\s*FACTURA\s*[:#-]?\s*([A-Z0-9][A-Z0-9\-]{2,29})",
        r"(?im)\bPREFIJO\s*[:#-]?\s*([A-Z]{1,8})\s+N[ÚU]MERO\s*[:#-]?\s*(\d{2,20})",
    ]

    for patron in patrones:
        coincidencia = re.search(patron, texto)
        if not coincidencia:
            continue

        if coincidencia.lastindex == 2:
            candidato = f"{coincidencia.group(1)}{coincidencia.group(2)}"
        else:
            candidato = coincidencia.group(1)

        candidato = str(candidato or "").strip()

        if _numero_factura_candidato_valido(candidato):
            return candidato

    return ""

def _extraer_tarifa_iva_factura(texto):
    coincidencia = re.search(
        r"(?im)\bIVA\b[^\n%]{0,40}?(\d{1,2}(?:[\.,]\d+)?)\s*%",
        texto
    )

    if coincidencia:
        valor = convertir_numero(
            coincidencia.group(1),
            None
        )

        if valor is not None:
            return float(
                valor
            )

    porcentajes = re.findall(
        r"(?<!\d)(\d{1,2}(?:[\.,]\d+)?)\s*%",
        texto
    )

    for porcentaje in porcentajes:
        valor = convertir_numero(
            porcentaje,
            None
        )

        if valor in (
            0,
            5,
            19
        ):
            return float(
                valor
            )

    return None

def _extraer_valor_iva_factura(texto):
    for linea in texto.splitlines():
        if "IVA" not in linea.upper():
            continue

        linea_sin_tarifas = re.sub(
            r"\d{1,2}(?:[.,]\d+)?\s*%",
            " ",
            linea,
        )
        numeros = re.findall(
            r"(?<!\w)(?:\$?\s*)?([0-9][0-9\.,]*)",
            linea_sin_tarifas,
        )

        valores = []

        for numero in numeros:
            valor = convertir_numero(
                numero,
                None
            )

            if valor is not None:
                valores.append(
                    float(valor)
                )

        if valores:
            return valores[-1]

    return _encontrar_valor_despues_etiqueta(
        texto,
        [
            r"\bVALOR\s+IVA\b",
            r"\bIVA\b",
            r"\bIMPUESTO\b",
        ]
    )

def _extraer_total_factura(texto):
    for patron in [
        r"(?im)\b(?:TOTAL\s+A\s+PAGAR|VALOR\s+A\s+PAGAR|TOTAL\s+FACTURA)\s*[:$-]*\s*(?:COP\s*)?\$?\s*([0-9][0-9\.,]*)",
        r"(?im)\bVALOR\s+TOTAL\s*[:$-]*\s*(?:COP\s*)?\$?\s*([0-9][0-9\.,]*)",
        r"(?im)\bTOTAL(?:\s+A\s+PAGAR)?\s*\$?\s*([0-9][0-9\.,]*)",
    ]:
        coincidencia = re.search(patron, texto)
        if coincidencia:
            valor = convertir_numero(coincidencia.group(1), None)
            if valor is not None:
                return float(valor)

    return None

def _extraer_base_factura(texto):
    valor = _encontrar_valor_despues_etiqueta(
        texto,
        [
            r"\bSUBTOTAL\b",
            r"\bSUBTOT\.?\b",
            r"\bBASE\s+GRAVABLE\b",
            r"\bBASE\b",
        ]
    )

    if valor is not None:
        return float(
            valor
        )

    return None

def _proveedor_candidato_valido(candidato):
    nombre = re.sub(r"\s+", " ", str(candidato or "")).strip()
    mayus = nombre.upper()

    if len(nombre) < 4:
        return False

    descartes = [
        "FACTURA", "ELECTRONICA", "ELECTRÓNICA", "RESPONSABLE",
        "DIRECCION", "DIRECCIÓN", "TELEFONO", "TELÉFONO", "EMAIL",
        "E-MAIL", "CORREO", "CLIENTE", "ADQUIRENTE", "REMISIÓN",
        "REMISION", "MEDIO DE PAGO", "FORMA DE PAGO", "CRV CONSTRUCCIONES",
        "CRV CONSTRUCTORA", "NIT", "TOTAL", "SUBTOTAL", "IVA",
    ]

    if any(palabra in mayus for palabra in descartes):
        return False

    if re.fullmatch(r"[\d\W]+", nombre):
        return False

    # Evita referencias/códigos cortos del encabezado.
    if len(nombre.split()) == 1 and re.search(r"\d", nombre):
        return False

    return True

def _extraer_proveedor_factura(texto, nit=""):
    lineas = [linea.strip() for linea in texto.splitlines() if linea.strip()]

    patrones_explicitos = [
        r"(?im)^(?:RAZ[ÓO]N\s+SOCIAL|PROVEEDOR|VENDEDOR|EMISOR|NOMBRE\s+DEL\s+EMISOR)\s*[:\-]\s*(.+)$",
    ]

    for patron in patrones_explicitos:
        coincidencia = re.search(patron, texto)
        if coincidencia:
            candidato = coincidencia.group(1).strip()
            if _proveedor_candidato_valido(candidato):
                return candidato[:220]

    nit_normalizado = _normalizar_identificacion_carga(nit)
    posiciones_nit = []

    for indice, linea in enumerate(lineas):
        if nit_normalizado and nit_normalizado in _normalizar_identificacion_carga(linea):
            posiciones_nit.append(indice)

    if not posiciones_nit:
        posiciones_nit = [
            indice
            for indice, linea in enumerate(lineas)
            if re.search(
                r"(?i)\b(?:NIT|N\.?\s*I\.?\s*T\.?|C\.?\s*C\.?|C[ÉE]DULA|IDENTIFICACI[ÓO]N)\b",
                linea,
            )
        ]

    for indice in posiciones_nit:
        for retroceso in (1, 2, 3, 4, 5):
            pos = indice - retroceso
            if pos < 0:
                continue
            candidato = lineas[pos]
            if _proveedor_candidato_valido(candidato):
                return candidato[:220]

    return ""

def _buscar_tercero_por_identificacion_carga(
    empresa_id,
    identificacion
):
    objetivo = _normalizar_identificacion_carga(
        identificacion
    )

    if not objetivo:
        return None

    terceros = (
        CRVTercero.query
        .filter_by(
            empresa_id=empresa_id
        )
        .all()
    )

    for tercero in terceros:
        if (
            _normalizar_identificacion_carga(
                tercero.identificacion
            )
            == objetivo
        ):
            return tercero

    return None

def _es_factura_duplicada_carga(
    empresa_id,
    identificacion,
    numero_documento
):
    numero = str(
        numero_documento or ""
    ).strip().upper()

    nit = _normalizar_identificacion_carga(
        identificacion
    )

    if not numero:
        return False, ""

    movimientos = (
        CRVMovimiento.query
        .filter(
            CRVMovimiento.empresa_id == empresa_id,
            db.func.upper(
                CRVMovimiento.numero_documento
            ) == numero
        )
        .all()
    )

    for movimiento in movimientos:
        if (
            not nit
            or _normalizar_identificacion_carga(
                movimiento.tercero_identificacion
            )
            == nit
        ):
            return (
                True,
                "Ya existe un movimiento CRV con esta factura."
            )

    obligaciones = (
        CRVCuentaPagar.query
        .filter(
            CRVCuentaPagar.empresa_id == empresa_id,
            db.func.upper(
                CRVCuentaPagar.numero_documento
            ) == numero
        )
        .all()
    )

    for obligacion in obligaciones:
        proveedor = getattr(
            obligacion,
            "proveedor",
            None
        )

        identificacion_proveedor = getattr(
            proveedor,
            "identificacion",
            ""
        )

        if (
            not nit
            or _normalizar_identificacion_carga(
                identificacion_proveedor
            )
            == nit
        ):
            return (
                True,
                "Ya existe una cuenta por pagar con esta factura."
            )

    return False, ""

def _validar_valores_factura_carga(base, tarifa, iva, total):
    alertas = []
    valores_originales = {
        "base": base,
        "tarifa": tarifa,
        "IVA": iva,
        "total": total,
    }

    def numero(valor):
        try:
            resultado = float(valor)
        except (TypeError, ValueError):
            return None
        return resultado if isfinite(resultado) else None

    base = numero(base)
    tarifa = numero(tarifa)
    iva = numero(iva)
    total = numero(total)

    valores_convertidos = {
        "base": base,
        "tarifa": tarifa,
        "IVA": iva,
        "total": total,
    }
    for nombre, valor_original in valores_originales.items():
        if valor_original is not None and valores_convertidos[nombre] is None:
            alertas.append(f"El valor de {nombre} no es un número válido.")

    if base is not None and base < 0:
        alertas.append("La base gravable no puede ser negativa.")

    if iva is not None and iva < 0:
        alertas.append("El IVA no puede ser negativo.")

    if total is not None and total <= 0:
        alertas.append("El total debe ser mayor a cero.")

    if tarifa is not None and tarifa < 0:
        alertas.append("La tarifa de IVA no puede ser negativa.")
    if tarifa is not None and tarifa > 100:
        alertas.append("La tarifa de IVA no puede superar el 100%.")

    if base is not None and tarifa is not None and iva is not None:
        iva_esperado = round(base * tarifa / 100, 2)
        tolerancia = max(2.0, abs(iva_esperado) * 0.002)
        if abs(iva - iva_esperado) > tolerancia:
            alertas.append(
                f"IVA inconsistente: con base {base:,.2f} y tarifa {tarifa:g}% "
                f"se esperan aproximadamente {iva_esperado:,.2f}."
            )

    if base is not None and iva is not None and total is not None:
        total_esperado = round(base + iva, 2)
        tolerancia = max(2.0, abs(total_esperado) * 0.002)
        if abs(total - total_esperado) > tolerancia:
            alertas.append(
                f"Total inconsistente: base + IVA = {total_esperado:,.2f}, "
                f"pero se leyó {total:,.2f}."
            )

    return alertas

def _estado_revision_carga(datos):
    faltantes = []

    if not str(datos.get("proveedor") or "").strip():
        faltantes.append("proveedor")
    if not str(datos.get("identificacion") or "").strip():
        faltantes.append("NIT")
    if not str(datos.get("numero_documento") or "").strip():
        faltantes.append("factura")
    if not str(datos.get("fecha_documento") or "").strip():
        faltantes.append("fecha")
    else:
        try:
            datetime.strptime(
                str(datos["fecha_documento"]),
                "%Y-%m-%d",
            )
        except ValueError:
            faltantes.append("fecha válida")
    tipo_iva = str(datos.get("tipo_iva") or "").strip().upper()
    if tipo_iva not in {
        "NO_APLICA",
        "DESCONTABLE",
        "MAYOR_VALOR_COSTO",
        "EXENTO",
        "EXCLUIDO",
    }:
        faltantes.append("tratamiento del IVA")
    if datos.get("base_gravable") is None:
        faltantes.append("base")
    if datos.get("valor_iva") is None:
        faltantes.append("IVA")
    if datos.get("total_documento") is None:
        faltantes.append("total")
    if (
        datos.get("valor_iva") is not None
        and float(datos.get("valor_iva") or 0) > 0
        and tipo_iva not in {"DESCONTABLE", "MAYOR_VALOR_COSTO"}
    ):
        if "tratamiento del IVA" not in faltantes:
            faltantes.append("tratamiento del IVA")
    if (
        datos.get("valor_iva") is not None
        and float(datos.get("valor_iva") or 0) > 0
        and datos.get("tarifa_iva") is None
    ):
        faltantes.append("tarifa IVA")

    alertas = _validar_valores_factura_carga(
        datos.get("base_gravable"),
        datos.get("tarifa_iva"),
        datos.get("valor_iva"),
        datos.get("total_documento"),
    )

    if datos.get("duplicado"):
        estado = "POSIBLE_DUPLICADO"
    elif faltantes or alertas:
        estado = "REVISION_REQUERIDA"
    elif datos.get("revision_manual"):
        estado = "LISTO_PARA_APROBAR"
    else:
        estado = "DATOS_EXTRAIDOS"

    return estado, faltantes, alertas

def _limpiar_monto_colombiano(cadena):
    """Limpia la puntuación ($ 1.500.000,00 -> 1500000.0)."""
    if not cadena:
        return 0.0
    val = re.sub(r'[^\d,\.]', '', str(cadena)).strip()
    if not val:
        return 0.0
    if "," in val and "." in val:
        if val.rfind(",") > val.rfind("."):
            val = val.replace(".", "").replace(",", ".")
        else:
            val = val.replace(",", "")
    elif "," in val:
        val = val.replace(",", ".")
    try:
        return float(val)
    except ValueError:
        return 0.0

def _extraer_montos_por_cuadrante_inferior(pagina):
    """
    Recorta la esquina inferior derecha del PDF (45% derecho, 45% inferior)
    y clasifica los números por magnitud financiera.
    """
    subtotal = 0.0
    valor_iva = 0.0
    total = 0.0

    try:
        ancho = pagina.width
        alto = pagina.height

        # Definir la caja de recorte (x0, top, x1, bottom)
        # Tomamos del 50% del ancho al 100%, y del 55% de la altura al 100%
        crop_box = (ancho * 0.50, alto * 0.55, ancho, alto)
        zona_inferior = pagina.crop(crop_box)
        texto_zona = zona_inferior.extract_text() or ""

        # Extraer todas las secuencias numéricas con formato de moneda/cifras
        candidatos_raw = re.findall(r'\$?\s*([0-9]{1,3}(?:[\.,][0-9]{3})*(?:[\.,][0-9]{2})?)', texto_zona)

        montos = []
        for cand in candidatos_raw:
            val = _limpiar_monto_colombiano(cand)
            # Descartar porcentajes (19.0), años (2026) o valores menores a $500
            if val > 500 and val != 19.0 and val != 19 and val not in [2024, 2025, 2026]:
                montos.append(val)

        # Eliminar duplicados manteniendo el orden
        montos_unicos = sorted(list(set(montos)), reverse=True)

        if len(montos_unicos) >= 2:
            total = montos_unicos[0]         # El número mayor es el TOTAL / NETO
            subtotal = montos_unicos[1]      # El segundo mayor es la BASE / SUBTOTAL

            # Si hay un tercer número menor, evaluamos si es el IVA
            if len(montos_unicos) >= 3 and (montos_unicos[2] < subtotal):
                valor_iva = montos_unicos[2]
            else:
                # Deducción matemática si no se extrajo el IVA explícito
                diferencia = round(total - subtotal, 2)
                if diferencia > 0 and abs(round(diferencia / subtotal, 2) - 0.19) < 0.04:
                    valor_iva = diferencia

        elif len(montos_unicos) == 1:
            total = montos_unicos[0]
            subtotal = total # Si no hay desglose, asume factura exenta/total único

    except Exception as e:
        print(f"Error recortando cuadrante inferior: {e}")

    return subtotal, valor_iva, total

def _analizar_factura_carga(empresa_id, ruta_archivo, nombre_original):
    extension = Path(nombre_original or ruta_archivo).suffix.lower()
    resultado = {
        "proveedor": "",
        "identificacion": "",
        "tipo_documento_tercero": "",
        "numero_documento": "",
        "fecha_documento": "",
        "base_gravable": None,
        "tarifa_iva": None,
        "tipo_iva": "",
        "valor_iva": None,
        "total_documento": None,
        "estado": "REVISION_REQUERIDA",
        "observaciones": "",
    }

    if extension != ".pdf":
        resultado["observaciones"] = (
            "La lectura automática de imágenes requiere OCR local; "
            "completa los datos manualmente antes de aprobar."
        )
        return resultado

    texto, error = _leer_texto_pdf(ruta_archivo)
    if error:
        resultado["observaciones"] = error
        return resultado

    texto = _limpiar_texto_factura(texto)
    identificacion = _extraer_nit_factura(texto)
    proveedor = _extraer_proveedor_factura(texto, identificacion)
    base = _extraer_base_factura(texto)
    tarifa = _extraer_tarifa_iva_factura(texto)
    iva = _extraer_valor_iva_factura(texto)
    total = _extraer_total_factura(texto)

    if base is None and total is not None and iva is not None and total >= iva:
        base = round(total - iva, 2)
    if iva is None and base is not None and total is not None:
        diferencia = round(total - base, 2)
        tarifa_inferida = round(diferencia / base * 100, 2) if base else 0
        if diferencia >= 0 and (
            diferencia == 0
            or any(abs(tarifa_inferida - tarifa_valida) <= 0.5 for tarifa_valida in (5, 19))
        ):
            iva = diferencia
            tarifa = tarifa_inferida
    if iva is not None and tarifa is None and base and iva > 0:
        tarifa_inferida = round(iva / base * 100, 2)
        tarifa = next(
            (valor for valor in (5.0, 19.0) if abs(tarifa_inferida - valor) <= 0.5),
            None,
        )
    if iva == 0 and tarifa is None:
        tarifa = 0.0
    if total is None and base is not None and iva is not None:
        total = round(base + iva, 2)

    resultado.update({
        "proveedor": proveedor,
        "identificacion": identificacion,
        "tipo_documento_tercero": _tipo_documento_factura(texto),
        "numero_documento": _extraer_numero_factura(texto),
        "fecha_documento": _extraer_fecha_factura(texto, nombre_original),
        "base_gravable": base,
        "tarifa_iva": tarifa,
        "tipo_iva": (
            ""
            if iva is not None and iva > 0
            else "NO_APLICA"
        ),
        "valor_iva": iva,
        "total_documento": total,
    })
    estado, faltantes, alertas = _estado_revision_carga(resultado)
    resultado["estado"] = estado
    observaciones = []
    if faltantes:
        observaciones.append("Revisar: " + ", ".join(faltantes) + ".")
    observaciones.extend(alertas)
    resultado["observaciones"] = " ".join(observaciones)
    return resultado

def _marcador_origen_factura(lote_id, archivo_id):
    return f"CARGA_INTELIGENTE:{lote_id}:{archivo_id}"


def obtener_cuenta_carga_inteligente(empresa_id, lote_id, archivo_id):
    return CRVCuentaPagar.query.filter_by(
        empresa_id=empresa_id,
        origen_registro="CARGA_INTELIGENTE",
        observaciones=_marcador_origen_factura(lote_id, archivo_id),
    ).first()


def registrar_factura_carga_inteligente(empresa_id, lote_id, item):
    cuenta_existente = obtener_cuenta_carga_inteligente(
        empresa_id,
        lote_id,
        item.get("archivo_id"),
    )
    if cuenta_existente:
        sincronizar_movimiento_compra_cxp(cuenta_existente)
        return cuenta_existente

    estado, faltantes, alertas = _estado_revision_carga(item)
    if estado != "LISTO_PARA_APROBAR":
        detalle = ", ".join(faltantes + alertas) or estado
        raise ValueError(f"El documento no está listo para aprobar: {detalle}")

    fecha = datetime.strptime(
        str(item["fecha_documento"]),
        "%Y-%m-%d",
    ).date()
    numero_documento = str(item["numero_documento"]).strip()
    identificacion = str(item["identificacion"]).strip()
    proveedor_nombre = str(item["proveedor"]).strip()

    if _es_factura_duplicada_carga(
        empresa_id,
        identificacion,
        numero_documento,
    )[0]:
        raise ValueError(
            f"La factura {numero_documento} ya existe para este proveedor."
        )

    proveedor = _buscar_tercero_por_identificacion_carga(
        empresa_id,
        identificacion,
    )
    if proveedor is None:
        tipo_documento = str(
            item.get("tipo_documento_tercero") or ""
        ).strip().upper()
        if tipo_documento not in {"NIT", "CEDULA"}:
            raise ValueError(
                "Selecciona si la identificación del nuevo proveedor es NIT o cédula."
            )
        proveedor = CRVTercero(
            empresa_id=empresa_id,
            tipo_tercero="PROVEEDOR",
            tipo_documento=tipo_documento,
            identificacion=identificacion,
            razon_social=proveedor_nombre,
            activo=True,
        )
        db.session.add(proveedor)
        db.session.flush()

    base = float(item["base_gravable"])
    iva = float(item["valor_iva"])
    total = float(item["total_documento"])
    tarifa = float(item.get("tarifa_iva") or 0)
    tipo_iva = str(item.get("tipo_iva") or "NO_APLICA").strip().upper()
    marcador = _marcador_origen_factura(
        lote_id,
        item.get("archivo_id"),
    )

    cuenta = CRVCuentaPagar(
        empresa_id=empresa_id,
        proveedor_id=proveedor.id,
        tipo_documento="FACTURA",
        numero_documento=numero_documento,
        fecha_documento=fecha,
        concepto=f"Factura de compra {numero_documento}",
        descripcion=f"Importada desde carga inteligente: {item.get('nombre_original', '')}",
        base_gravable=base,
        tipo_iva=tipo_iva,
        tarifa_iva=tarifa,
        valor_iva=iva,
        valor_bruto=total,
        valor_neto=total,
        total_pagado=0,
        saldo_pendiente=total,
        categoria="COMPRA",
        estado="PENDIENTE",
        observaciones=marcador,
        origen_registro="CARGA_INTELIGENTE",
        usuario_registro=str(session.get("usuario", "")),
    )
    cuenta.recalcular_estado()
    db.session.add(cuenta)
    db.session.flush()
    sincronizar_movimiento_compra_cxp(cuenta)
    return cuenta

__all__ = [
    "EXTENSIONES_CARGA_INTELIGENTE",
    "TAMANO_MAXIMO_ARCHIVO_CARGA",
    "_analizar_factura_carga",
    "_archivo_carga_valido",
    "_buscar_tercero_por_identificacion_carga",
    "_carpeta_carga_inteligente",
    "_encontrar_valor_despues_etiqueta",
    "_es_factura_duplicada_carga",
    "_estado_revision_carga",
    "_extraer_base_factura",
    "_extraer_fecha_factura",
    "_extraer_montos_por_cuadrante_inferior",
    "_extraer_nit_factura",
    "_extraer_numero_factura",
    "_extraer_proveedor_factura",
    "_extraer_tarifa_iva_factura",
    "_extraer_total_factura",
    "_extraer_valor_iva_factura",
    "_guardar_manifest_carga",
    "_leer_manifest_carga",
    "_leer_texto_pdf",
    "_limpiar_monto_colombiano",
    "_limpiar_texto_factura",
    "_listar_lotes_carga_inteligente",
    "_normalizar_identificacion_carga",
    "_numero_factura_candidato_valido",
    "_proveedor_candidato_valido",
    "_ruta_lote_carga",
    "_validar_valores_factura_carga",
    "_tipo_documento_factura",
    "obtener_cuenta_carga_inteligente",
    "registrar_factura_carga_inteligente",
]
