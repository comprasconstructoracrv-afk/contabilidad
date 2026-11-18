"""CRV Movimientos routes."""

from datetime import date
import datetime as dt
import pandas as pd

import openpyxl

from .crv_core import (
    CRVMovimiento,
    CRVTercero,
    Sede,
    _asignar_comprobante_permanente,
    calcular_iva_formulario,
    convertir_fecha,
    convertir_numero,
    crear_o_actualizar_tercero_desde_formulario,
    crv_bp,
    db,
    flash,
    proteger_crv,
    redirect,
    render_template,
    request,
    session,
)

@crv_bp.route("/movimientos")
def movimientos():

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    empresa_nombre = session.get(
        "empresa_nombre",
        "CRV CONSTRUCTORA"
    )

    mes = request.args.get(
        "mes",
        ""
    ).strip()

    sede_id = request.args.get(
        "sede_id",
        ""
    ).strip()

    tipo = request.args.get(
        "tipo",
        ""
    ).strip().upper()

    tercero = request.args.get(
        "tercero",
        ""
    ).strip()

    query = CRVMovimiento.query.filter_by(
        empresa_id=empresa_id
    )

    if sede_id.isdigit():

        query = query.filter_by(
            sede_id=int(sede_id)
        )

    if tipo:
        tipo_limpio = (
            tipo.strip()
            .upper()
            .replace("_", " ")
            .replace("Á", "A")
            .replace("É", "E")
            .replace("Í", "I")
            .replace("Ó", "O")
            .replace("Ú", "U")
        )

        col_normalizada = db.func.upper(db.func.trim(CRVMovimiento.tipo))
        for origen, destino in (
            ("_", " "),
            ("\n", " "),
            ("\r", " "),
            ("\t", " "),
            ("  ", " "),
            ("Á", "A"),
            ("É", "E"),
            ("Í", "I"),
            ("Ó", "O"),
            ("Ú", "U"),
        ):
            col_normalizada = db.func.replace(col_normalizada, origen, destino)

        if tipo_limpio == "NOMINA OBRA":
            query = query.filter(
                db.and_(
                    col_normalizada.like("%NOMINA%"),
                    col_normalizada.like("%OBRA%"),
                )
            )
        elif tipo_limpio == "NOMINA AFILIADOS":
            query = query.filter(
                db.and_(
                    col_normalizada.like("%NOMINA%"),
                    ~col_normalizada.like("%OBRA%"),
                )
            )
        else:
            query = query.filter(col_normalizada == tipo_limpio)

    if tercero:

        query = query.filter(
            CRVMovimiento.tercero_nombre.ilike(
                f"%{tercero}%"
            )
        )

    if mes:

        try:

            anio_texto, mes_texto = mes.split("-")

            query = query.filter(
                db.extract(
                    "year",
                    CRVMovimiento.fecha
                ) == int(anio_texto),

                db.extract(
                    "month",
                    CRVMovimiento.fecha
                ) == int(mes_texto)
            )

        except (ValueError, TypeError):
            pass

    registros = query.order_by(
        CRVMovimiento.fecha.desc(),
        CRVMovimiento.id.desc()
    ).all()

    sedes = Sede.query.filter_by(
        empresa_id=empresa_id
    ).order_by(
        Sede.nombre.asc()
    ).all()

    # Calculo de indicadores de movimientos por tipo y categoría
    totales = {
        "ingresos": 0.0,
        "compras": 0.0,
        "gastos_operativos": 0.0,
        "nomina_obra": 0.0,
        "nomina_afiliados": 0.0,
        "anticipos": 0.0,
    }

    for m in registros:
        val = float(m.valor or 0)
        t = (m.tipo or "").strip().upper()
        cat = (m.categoria or "").strip().upper()
        sub = (m.subcategoria or "").strip().upper()
        texto_clasificacion = f"{t} {cat} {sub}"

        if t == "INGRESO":
            totales["ingresos"] += val
        elif t == "COMPRA":
            totales["compras"] += val
        elif any(p in texto_clasificacion for p in ("ANTICIPO", "PRESTAMO", "PRÉSTAMO")):
            totales["anticipos"] += val
        elif any(p in texto_clasificacion for p in ("NOMINA", "NÓMINA", "SEGURIDAD SOCIAL", "SALARIO")):
            if "OBRA" in texto_clasificacion:
                totales["nomina_obra"] += val
            else:
                totales["nomina_afiliados"] += val
        else:
            totales["gastos_operativos"] += val

    totales["nomina_total"] = totales["nomina_obra"] + totales["nomina_afiliados"]

    reporte_excel = session.pop("reporte_importacion_excel", None)

    return render_template(
        "contabilidad/crv_movimientos.html",

        empresa_nombre=empresa_nombre,
        movimientos=registros,
        sedes=sedes,
        mes_actual=mes,
        sede_actual=sede_id,
        tipo_actual=tipo,
        tercero_actual=tercero,
        reporte_excel=reporte_excel,
        totales=totales
    )

@crv_bp.route(
    "/movimientos/nuevo",
    methods=["GET", "POST"]
)
def nuevo_movimiento():

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    empresa_nombre = session.get(
        "empresa_nombre",
        "CRV CONSTRUCTORA"
    )

    sedes = Sede.query.filter_by(
        empresa_id=empresa_id
    ).order_by(
        Sede.nombre.asc()
    ).all()

    terceros = CRVTercero.query.filter_by(
        empresa_id=empresa_id,
        activo=True
    ).order_by(
        CRVTercero.razon_social.asc()
    ).all()

    if request.method == "POST":

        fecha = convertir_fecha(
            request.form.get("fecha")
        )

        if not fecha:

            flash(
                "Debes indicar la fecha contable del movimiento.",
                "error"
            )

            return render_template(
                "contabilidad/crv_nuevo_movimiento.html",
                empresa_nombre=empresa_nombre,
                sedes=sedes,
                terceros=terceros,
                movimiento=None,
                modo="nuevo"
            )

        tipo = request.form.get(
            "tipo",
            ""
        ).strip().upper()

        categoria = request.form.get(
            "categoria",
            ""
        ).strip()

        concepto = request.form.get(
            "concepto",
            ""
        ).strip()

        iva_datos = calcular_iva_formulario(
            request.form
        )

        valor = iva_datos[
            "total_documento"
        ]

        if not tipo:

            flash(
                "Debes seleccionar el tipo de movimiento.",
                "error"
            )

            return redirect(
                "/crv/movimientos/nuevo"
            )

        if not categoria:
            categoria = "OTRO"

        if not concepto:

            flash(
                "Debes escribir el concepto del movimiento.",
                "error"
            )

            return redirect(
                "/crv/movimientos/nuevo"
            )

        tercero_obj = crear_o_actualizar_tercero_desde_formulario(
            empresa_id,
            request.form
        )

        sede_id_texto = request.form.get(
            "sede_id",
            ""
        ).strip()

        sede_id = (
            int(sede_id_texto)
            if sede_id_texto.isdigit()
            else None
        )

        descuento = convertir_numero(
            request.form.get("descuento")
        )

        retencion = convertir_numero(
            request.form.get("retencion")
        )

        otros_descuentos = convertir_numero(
            request.form.get(
                "otros_descuentos"
            )
        )

        valor_neto = max(
            0,
            valor
            - descuento
            - retencion
            - otros_descuentos
        )

        movimiento = CRVMovimiento(

            empresa_id=empresa_id,
            sede_id=sede_id,

            fecha=fecha,

            tipo=tipo,

            categoria=categoria,

            subcategoria=request.form.get(
                "subcategoria",
                ""
            ).strip(),

            concepto=concepto,

            descripcion=request.form.get(
                "descripcion",
                ""
            ).strip(),

            tercero_id=(
                tercero_obj.id
                if tercero_obj
                else None
            ),

            tercero_nombre=(
                tercero_obj.razon_social
                if tercero_obj
                else request.form.get(
                    "tercero_nombre",
                    ""
                ).strip()
            ),

            tercero_identificacion=(
                tercero_obj.identificacion
                if tercero_obj
                else request.form.get(
                    "tercero_identificacion",
                    ""
                ).strip()
            ),

            tercero_direccion=(
                tercero_obj.direccion
                if tercero_obj
                else request.form.get(
                    "tercero_direccion",
                    ""
                ).strip()
            ),

            tercero_email=(
                tercero_obj.email
                if tercero_obj
                else request.form.get(
                    "tercero_email",
                    ""
                ).strip()
            ),

            tercero_telefono=(
                (
                    tercero_obj.celular
                    or tercero_obj.telefono
                )
                if tercero_obj
                else request.form.get(
                    "tercero_celular",
                    ""
                ).strip()
            ),

            tercero_contacto=(
                tercero_obj.contacto
                if tercero_obj
                else request.form.get(
                    "tercero_contacto",
                    ""
                ).strip()
            ),

            tipo_documento=request.form.get(
                "tipo_documento",
                ""
            ).strip(),

            numero_documento=request.form.get(
                "numero_documento",
                ""
            ).strip(),

            numero_soporte=request.form.get(
                "numero_soporte",
                ""
            ).strip(),

            fecha_documento=convertir_fecha(
                request.form.get(
                    "fecha_documento"
                )
            ),

            fecha_vencimiento=convertir_fecha(
                request.form.get(
                    "fecha_vencimiento"
                )
            ),

            base_gravable=iva_datos["base_gravable"],
            tipo_iva=iva_datos["tipo_iva"],
            tarifa_iva=iva_datos["tarifa_iva"],
            valor_iva=iva_datos["valor_iva"],
            valor=valor,
            descuento=descuento,
            retencion=retencion,
            otros_descuentos=otros_descuentos,
            valor_neto=valor_neto,

            forma_pago=request.form.get(
                "forma_pago",
                ""
            ).strip(),

            cuenta=request.form.get(
                "cuenta",
                ""
            ).strip(),

            cuenta_destino=request.form.get(
                "cuenta_destino",
                ""
            ).strip(),

            beneficiario=request.form.get(
                "beneficiario",
                ""
            ).strip(),

            referencia_pago=request.form.get(
                "referencia_pago",
                ""
            ).strip(),

            proyecto=request.form.get(
                "proyecto",
                ""
            ).strip(),

            centro_costo=request.form.get(
                "centro_costo",
                ""
            ).strip(),

            obra=request.form.get(
                "obra",
                ""
            ).strip(),

            observaciones=request.form.get(
                "observaciones",
                ""
            ).strip(),

            revisado=False,

            estado="ACTIVO",

            origen_registro="SISTEMA",

            usuario_registro=str(
                session.get(
                    "usuario",
                    ""
                )
            )
        )

        _asignar_comprobante_permanente(
            movimiento
        )

        db.session.add(movimiento)

        db.session.commit()

        flash(
            "Movimiento CRV registrado correctamente.",
            "success"
        )

        return redirect(
            "/crv/movimientos"
        )

    return render_template(
        "contabilidad/crv_nuevo_movimiento.html",

        empresa_nombre=empresa_nombre,

        sedes=sedes,

        terceros=terceros,

        movimiento=None,

        modo="nuevo"
    )
@crv_bp.route(
    "/movimientos/editar/<int:movimiento_id>",
    methods=["GET", "POST"]
)
def editar_movimiento(movimiento_id):

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    empresa_nombre = session.get(
        "empresa_nombre",
        "CRV CONSTRUCTORA"
    )

    movimiento = CRVMovimiento.query.get_or_404(
        movimiento_id
    )

    if movimiento.empresa_id != empresa_id:

        return redirect(
            "/crv/movimientos"
        )

    if movimiento.origen_registro in (
        "CUENTAS_POR_PAGAR",
        "PAGO_CUENTA_POR_PAGAR"
    ):

        flash(
            "Este movimiento fue generado por Cuentas por pagar y debe administrarse desde ese módulo para conservar los saldos correctos.",
            "warning"
        )

        return redirect(
            "/crv/cuentas-por-pagar"
        )

    sedes = Sede.query.filter_by(
        empresa_id=empresa_id
    ).order_by(
        Sede.nombre.asc()
    ).all()

    terceros = CRVTercero.query.filter_by(
        empresa_id=empresa_id,
        activo=True
    ).order_by(
        CRVTercero.razon_social.asc()
    ).all()

    # -------------------------------------------------------------------------
    # 1. BÚSQUEDA DEL TERCERO ACTUALIZADO DESDE LA BD
    # -------------------------------------------------------------------------
    tercero_actual = None
    if movimiento.tercero_id:
        tercero_actual = CRVTercero.query.get(movimiento.tercero_id)
    elif movimiento.tercero_identificacion:
        tercero_actual = CRVTercero.query.filter_by(
            empresa_id=empresa_id,
            identificacion=movimiento.tercero_identificacion
        ).first()

    if request.method == "POST":

        fecha = convertir_fecha(
            request.form.get("fecha")
        )

        if not fecha:

            flash(
                "La fecha contable es obligatoria.",
                "error"
            )

            return redirect(
                f"/crv/movimientos/editar/{movimiento_id}"
            )

        tercero_obj = crear_o_actualizar_tercero_desde_formulario(
            empresa_id,
            request.form
        )

        movimiento.fecha = fecha

        movimiento.tipo = request.form.get(
            "tipo",
            ""
        ).strip().upper()

        movimiento.categoria = request.form.get(
            "categoria",
            "OTRO"
        ).strip()

        movimiento.subcategoria = request.form.get(
            "subcategoria",
            ""
        ).strip()

        movimiento.concepto = request.form.get(
            "concepto",
            ""
        ).strip()

        movimiento.descripcion = request.form.get(
            "descripcion",
            ""
        ).strip()

        sede_id_texto = request.form.get(
            "sede_id",
            ""
        ).strip()

        movimiento.sede_id = (
            int(sede_id_texto)
            if sede_id_texto.isdigit()
            else None
        )

        # -------------------------------------------------------------------------
        # 2. SE AGREGA LA ASIGNACIÓN DE TIPO Y DOCUMENTO DEL TERCERO EN EL MOVIMIENTO
        # -------------------------------------------------------------------------
        if tercero_obj:
            movimiento.tercero_id = tercero_obj.id
            movimiento.tercero_nombre = tercero_obj.razon_social
            movimiento.tercero_identificacion = tercero_obj.identificacion
            movimiento.tercero_direccion = tercero_obj.direccion
            movimiento.tercero_email = tercero_obj.email
            movimiento.tercero_telefono = (
                tercero_obj.celular
                or tercero_obj.telefono
            )
            movimiento.tercero_contacto = tercero_obj.contacto
            
            # ASIGNACIONES CLAVE AGREGADAS:
            movimiento.tipo_tercero = tercero_obj.tipo_tercero
            movimiento.tipo_documento = tercero_obj.tipo_documento
        else:
            movimiento.tipo_tercero = request.form.get("tipo_tercero", "TERCERO").strip()
            movimiento.tipo_documento = request.form.get("tipo_documento_tercero", "NIT").strip()

        movimiento.numero_documento = request.form.get(
            "numero_documento",
            ""
        ).strip()

        movimiento.numero_soporte = request.form.get(
            "numero_soporte",
            ""
        ).strip()

        movimiento.fecha_documento = convertir_fecha(
            request.form.get(
                "fecha_documento"
            )
        )

        movimiento.fecha_vencimiento = convertir_fecha(
            request.form.get(
                "fecha_vencimiento"
            )
        )

        iva_datos = calcular_iva_formulario(
            request.form
        )

        movimiento.base_gravable = iva_datos[
            "base_gravable"
        ]
        movimiento.tipo_iva = iva_datos[
            "tipo_iva"
        ]
        movimiento.tarifa_iva = iva_datos[
            "tarifa_iva"
        ]
        movimiento.valor_iva = iva_datos[
            "valor_iva"
        ]
        movimiento.valor = iva_datos[
            "total_documento"
        ]

        movimiento.descuento = convertir_numero(
            request.form.get("descuento")
        )

        movimiento.retencion = convertir_numero(
            request.form.get("retencion")
        )

        movimiento.otros_descuentos = convertir_numero(
            request.form.get(
                "otros_descuentos"
            )
        )

        movimiento.recalcular_valor_neto()

        movimiento.forma_pago = request.form.get(
            "forma_pago",
            ""
        ).strip()

        movimiento.cuenta = request.form.get(
            "cuenta",
            ""
        ).strip()

        movimiento.cuenta_destino = request.form.get(
            "cuenta_destino",
            ""
        ).strip()

        movimiento.beneficiario = request.form.get(
            "beneficiario",
            ""
        ).strip()

        movimiento.referencia_pago = request.form.get(
            "referencia_pago",
            ""
        ).strip()

        movimiento.proyecto = request.form.get(
            "proyecto",
            ""
        ).strip()

        movimiento.centro_costo = request.form.get(
            "centro_costo",
            ""
        ).strip()

        movimiento.obra = request.form.get(
            "obra",
            ""
        ).strip()

        movimiento.observaciones = request.form.get(
            "observaciones",
            ""
        ).strip()

        db.session.commit()

        flash(
            "Movimiento actualizado correctamente.",
            "success"
        )

        return redirect(
            "/crv/movimientos"
        )

    return render_template(
        "contabilidad/crv_nuevo_movimiento.html",

        empresa_nombre=empresa_nombre,

        sedes=sedes,

        terceros=terceros,

        movimiento=movimiento,

        tercero_actual=tercero_actual,  # Pasa los datos vigentes del tercero a la vista

        modo="editar"
    )

@crv_bp.route(
    "/movimientos/eliminar/<int:movimiento_id>",
    methods=["POST"]
)
def eliminar_movimiento(movimiento_id):

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    movimiento = CRVMovimiento.query.get_or_404(
        movimiento_id
    )

    if movimiento.empresa_id != empresa_id:

        return redirect(
            "/crv/movimientos"
        )

    if movimiento.origen_registro in (
        "CUENTAS_POR_PAGAR",
        "PAGO_CUENTA_POR_PAGAR"
    ):

        flash(
            "Este movimiento fue generado por Cuentas por pagar y no debe eliminarse desde Movimientos. Usa el módulo de Cuentas por pagar.",
            "warning"
        )

        return redirect(
            "/crv/cuentas-por-pagar"
        )

    db.session.delete(movimiento)

    db.session.commit()

    flash(
        "Movimiento eliminado correctamente.",
        "success"
    )

    return redirect(
        "/crv/movimientos"
    )

@crv_bp.route("/movimientos/importar-excel", methods=["POST"])
def importar_movimientos_excel():
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    archivo = request.files.get("archivo_excel")

    if not archivo or not archivo.filename:
        flash("Debes seleccionar un archivo Excel válido.", "error")
        return redirect("/crv/movimientos")

    try:
        df_raw = pd.read_excel(archivo, header=None)

        fila_header = None
        for idx, row in df_raw.iterrows():
            valores = [
                str(v).strip().upper().replace("\n", "").replace(" ", "_")
                for v in row.values
                if pd.notna(v)
            ]
            if "FECHA" in valores and "TIPO" in valores:
                fila_header = idx
                break

        if fila_header is None:
            flash(
                "No se encontraron las columnas 'FECHA' y 'TIPO' en el archivo Excel.",
                "error",
            )
            return redirect("/crv/movimientos")

        columnas_limpias = [
            str(v).strip().upper().replace("\n", "").replace(" ", "_")
            if pd.notna(v)
            else f"COL_{i}"
            for i, v in enumerate(df_raw.iloc[fila_header])
        ]
        df = df_raw.iloc[fila_header + 1 :].copy()
        df.columns = columnas_limpias
        df = df.dropna(how="all")

        def obtener_valor(fila, *nombres):
            for nombre in nombres:
                if nombre in fila.index and pd.notna(fila[nombre]):
                    val = fila[nombre]
                    if str(val).strip() != "":
                        return val
            return None

        def limpiar_texto_entero(val):
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return ""
            if isinstance(val, float) and val.is_integer():
                return str(int(val))
            texto = str(val).strip()
            return texto[:-2] if texto.endswith(".0") else texto

        def parsear_fecha_excel(valor):
            if valor is None or (isinstance(valor, float) and pd.isna(valor)):
                return None
            if isinstance(valor, (dt.datetime, dt.date, pd.Timestamp)):
                return valor.date() if hasattr(valor, "date") else valor

            texto = str(valor).strip().split(" ")[0]
            if not texto:
                return None

            for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d", "%d-%m-%y", "%d/%m/%y"):
                try:
                    return dt.datetime.strptime(texto, fmt).date()
                except ValueError:
                    continue

            return convertir_fecha(texto)

        creados = 0
        errores = []
        documentos_lote = set()

        for idx, fila in df.iterrows():
            num_fila_excel = idx + 1

            # --- 1. EXTRAER REFERENCIA Y NUMERO DE DOCUMENTO (Columnas O, P y Q) ---
            tipo_documento = str(
                obtener_valor(
                    fila,
                    "TIPO_NUMERO_DOCUMENTO",
                    "TIPO_NUMERO_DOCUMENT",
                    "TIPO_DOCUMENTO_SOPORTE",
                    "TIPO_DOCUMENTO",
                )
                or ""
            ).strip().upper()

            prefijo_doc = limpiar_texto_entero(obtener_valor(fila, "NUMERO_DOCUMENTO")).upper().rstrip("-")
            num_doc = ""

            if "NUMERO_DOCUMENTO" in fila.index:
                pos_col_doc = list(fila.index).index("NUMERO_DOCUMENTO")
                if pos_col_doc + 1 < len(fila.index):
                    nombre_col_siguiente = str(fila.index[pos_col_doc + 1])
                    if nombre_col_siguiente.startswith("COL_"):
                        num_doc = limpiar_texto_entero(fila.iloc[pos_col_doc + 1]).lstrip("-")

            if prefijo_doc and num_doc:
                numero_documento = f"{prefijo_doc}-{num_doc}"
            else:
                numero_documento = prefijo_doc or num_doc

            numero_soporte = limpiar_texto_entero(obtener_valor(fila, "NUMERO_SOPORTE"))
            identificacion = limpiar_texto_entero(obtener_valor(fila, "TERCERO_IDENTIFICACION"))

            # Etiqueta para identificar exactamente la fila si falla
            etiqueta_fila = f"Fila {num_fila_excel}"
            datos_ref = " | ".join(
                filter(
                    None,
                    [
                        f"Doc: {numero_documento}" if numero_documento else "",
                        f"NIT/CC: {identificacion}" if identificacion else "",
                    ],
                )
            )
            if datos_ref:
                etiqueta_fila += f" ({datos_ref})"

            # --- 2. VALIDAR FECHA Y TIPO ---
            fecha_raw = obtener_valor(fila, "FECHA")
            fecha = parsear_fecha_excel(fecha_raw)
            if not fecha:
                errores.append(f"{etiqueta_fila}: Fecha inválida o vacía ('{fecha_raw}').")
                continue

            tipo = str(obtener_valor(fila, "TIPO") or "").strip().upper()
            if not tipo:
                errores.append(f"{etiqueta_fila}: Falta el TIPO de movimiento.")
                continue

            # --- 3. AUDITORÍA DE DUPLICIDAD ---
            if numero_documento:
                clave_lote = (identificacion.upper(), numero_documento.upper())
                if clave_lote in documentos_lote:
                    errores.append(
                        f"{etiqueta_fila}: Documento '{numero_documento}' duplicado dentro del mismo archivo Excel."
                    )
                    continue

                consulta_dup = CRVMovimiento.query.filter_by(
                    empresa_id=empresa_id,
                    estado="ACTIVO",
                ).filter(
                    db.func.upper(CRVMovimiento.numero_documento) == numero_documento.upper()
                )

                if identificacion:
                    consulta_dup = consulta_dup.filter(
                        CRVMovimiento.tercero_identificacion == identificacion
                    )

                existente = consulta_dup.first()
                if existente:
                    fecha_ex = existente.fecha.strftime("%d-%m-%Y") if existente.fecha else "sin fecha"
                    errores.append(
                        f"{etiqueta_fila}: No es posible cargar el documento '{numero_documento}' porque ya existe activo (Fecha: {fecha_ex}, Valor: ${existente.valor:,.0f})."
                    )
                    continue

                documentos_lote.add(clave_lote)

            if numero_soporte:
                soporte_existente = CRVMovimiento.query.filter_by(
                    empresa_id=empresa_id,
                    estado="ACTIVO",
                ).filter(
                    db.func.upper(CRVMovimiento.numero_soporte) == numero_soporte.upper()
                ).first()

                if soporte_existente:
                    errores.append(
                        f"{etiqueta_fila}: No es posible cargar porque el número de soporte '{numero_soporte}' ya está registrado."
                    )
                    continue

            # --- 4. CATEGORIA, CONCEPTO Y TERCERO ---
            categoria = str(obtener_valor(fila, "CATEGORIA") or "OTRO").strip().upper()
            subcategoria = str(obtener_valor(fila, "SUBCATEGORIA") or "").strip()
            proyecto_obra = str(obtener_valor(fila, "PROYECTO_OBRA", "PROYECTO") or "").strip()
            concepto = str(obtener_valor(fila, "CONCEPTO") or "").strip() or f"{tipo} - {categoria}"

            tercero_obj = None
            if identificacion:
                tercero_obj = CRVTercero.query.filter_by(
                    empresa_id=empresa_id,
                    identificacion=identificacion,
                ).first()

            # --- 5. VALORES E IVA ---
            base_gravable = float(convertir_numero(obtener_valor(fila, "BASE_GRAVABLE")) or 0)
            tarifa_iva = float(convertir_numero(obtener_valor(fila, "TARIFA_IVA")) or 0)
            valor_iva = float(convertir_numero(obtener_valor(fila, "VALOR_IVA")) or 0)
            total_doc = float(convertir_numero(obtener_valor(fila, "TOTAL_DOCUMENTO")) or 0)
            retencion = float(convertir_numero(obtener_valor(fila, "RETENCION")) or 0)
            otro_descuento = float(
                convertir_numero(obtener_valor(fila, "OTRO_DESCUENTO", "OTROS_DESCUENTOS")) or 0
            )

            if total_doc > 0 and base_gravable <= 0:
                base_gravable = round(max(0.0, total_doc - valor_iva), 2)

            if base_gravable > 0 and tarifa_iva > 0 and valor_iva <= 0:
                valor_iva = round(base_gravable * (tarifa_iva / 100.0), 2)

            if total_doc <= 0 and (base_gravable > 0 or valor_iva > 0):
                total_doc = round(base_gravable + valor_iva, 2)

            if valor_iva > 0 and base_gravable > 0 and tarifa_iva <= 0:
                porcentaje_calc = (valor_iva / base_gravable) * 100.0
                for tarifa_estandar in (19.0, 5.0, 8.0, 16.0):
                    if abs(porcentaje_calc - tarifa_estandar) <= 0.3:
                        tarifa_iva = tarifa_estandar
                        break
                else:
                    tarifa_iva = round(porcentaje_calc, 2)

            tipo_iva = "DESCONTABLE" if valor_iva > 0 else "NO_APLICA"
            valor_neto = round(max(0.0, total_doc - retencion - otro_descuento), 2)

            forma_pago = str(obtener_valor(fila, "FORMA_PAGO") or "TRANSFERENCIA").strip().upper()
            cuenta = str(obtener_valor(fila, "CUENTA_ORIGEN", "CUENTA") or "71800002023").strip()
            observaciones = str(obtener_valor(fila, "OBSERVACIONES") or "").strip()

            movimiento = CRVMovimiento(
                empresa_id=empresa_id,
                fecha=fecha,
                tipo=tipo,
                categoria=categoria,
                subcategoria=subcategoria,
                concepto=concepto,
                tercero_id=tercero_obj.id if tercero_obj else None,
                tercero_nombre=tercero_obj.razon_social if tercero_obj else "",
                tercero_identificacion=tercero_obj.identificacion if tercero_obj else identificacion,
                tercero_direccion=tercero_obj.direccion if tercero_obj else "",
                tercero_email=tercero_obj.email if tercero_obj else "",
                tercero_telefono=(tercero_obj.celular or tercero_obj.telefono) if tercero_obj else "",
                tercero_contacto=tercero_obj.contacto if tercero_obj else "",
                tipo_documento=tipo_documento,
                numero_documento=numero_documento,
                numero_soporte=numero_soporte,
                base_gravable=base_gravable,
                tipo_iva=tipo_iva,
                tarifa_iva=tarifa_iva,
                valor_iva=valor_iva,
                valor=total_doc,
                descuento=0.0,
                retencion=retencion,
                otros_descuentos=otro_descuento,
                valor_neto=valor_neto,
                forma_pago=forma_pago,
                cuenta=cuenta,
                cuenta_destino=tercero_obj.numero_cuenta if tercero_obj else "",
                beneficiario=tercero_obj.razon_social if tercero_obj else "",
                proyecto=proyecto_obra,
                obra=proyecto_obra,
                observaciones=observaciones,
                revisado=False,
                estado="ACTIVO",
                origen_registro="EXCEL",
                usuario_registro=str(session.get("usuario", "")),
            )

            _asignar_comprobante_permanente(movimiento)
            db.session.add(movimiento)
            creados += 1

        db.session.commit()
        session["reporte_importacion_excel"] = {
            "creados": creados,
            "errores": errores,
        }

    except Exception as e:
        db.session.rollback()
        flash(f"Error al procesar el archivo Excel: {str(e)}", "error")

    return redirect("/crv/movimientos")

__all__ = ['movimientos', 'nuevo_movimiento', 'editar_movimiento', 'eliminar_movimiento', 'importar_movimientos_excel']
