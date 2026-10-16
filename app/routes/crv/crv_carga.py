"""CRV Carga routes."""

from .crv_core import (
    Path,
    TAMANO_MAXIMO_ARCHIVO_CARGA,
    _analizar_factura_carga,
    _archivo_carga_valido,
    _buscar_tercero_por_identificacion_carga,
    _es_factura_duplicada_carga,
    _estado_revision_carga,
    _guardar_manifest_carga,
    _leer_manifest_carga,
    _listar_lotes_carga_inteligente,
    _ruta_lote_carga,
    convertir_fecha,
    convertir_numero,
    convertir_porcentaje,
    crv_bp,
    current_app,
    datetime,
    flash,
    _estado_revision_carga,
    _es_factura_duplicada_carga,
    _guardar_manifest_carga,
    _buscar_tercero_por_identificacion_carga,
    obtener_cuenta_carga_inteligente,
    registrar_factura_carga_inteligente,
    db,
    proteger_crv,
    redirect,
    render_template,
    request,
    secure_filename,
    send_file,
    session,
    uuid,
)

@crv_bp.route(
    "/carga-inteligente/<lote_id>/procesar",
    methods=["POST"]
)
def carga_inteligente_procesar(lote_id):
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    manifest = _leer_manifest_carga(empresa_id, lote_id)

    if not manifest or manifest.get("estado") != "PENDIENTE_REVISION":
        flash("El lote solicitado no está disponible para lectura.", "warning")
        return redirect(f"/crv/carga-inteligente?lote={lote_id}")

    carpeta = _ruta_lote_carga(empresa_id, lote_id)
    procesados = 0
    archivos = manifest.get("archivos", [])

    for item in archivos:
        ruta = carpeta / str(item.get("nombre_guardado", ""))

        if not ruta.exists():
            item["estado"] = "ARCHIVO_NO_ENCONTRADO"
            item["observaciones"] = "El archivo físico no fue encontrado en el servidor."
            continue

        analisis = _analizar_factura_carga(
            empresa_id,
            ruta,
            item.get("nombre_original", "")
        )

        if analisis:
            item.update(analisis)
            item["fecha_lectura"] = datetime.now().isoformat(timespec="seconds")

            tercero = _buscar_tercero_por_identificacion_carga(
                empresa_id, item.get("identificacion", "")
            )
            item["tercero_existente"] = bool(tercero)
            if tercero:
                item["tercero_id"] = tercero.id

            procesados += 1

    manifest["fecha_ultima_lectura"] = datetime.now().isoformat(timespec="seconds")
    _guardar_manifest_carga(empresa_id, lote_id, manifest)

    flash(f"Lectura finalizada con éxito para {procesados} documento(s).", "success")
    return redirect(f"/crv/carga-inteligente?lote={lote_id}")

@crv_bp.route(
    "/carga-inteligente/<lote_id>/guardar-masivo",
    methods=["POST"]
)
def carga_inteligente_guardar_masivo(lote_id):
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    manifest = _leer_manifest_carga(empresa_id, lote_id)

    if not manifest:
        flash("El lote no existe o venció.", "error")
        return redirect("/crv/carga-inteligente")

    if manifest.get("estado") != "PENDIENTE_REVISION":
        flash("Este lote ya fue aprobado y no puede modificarse.", "warning")
        return redirect(f"/crv/carga-inteligente?lote={lote_id}")

    _actualizar_revision_masiva(empresa_id, manifest)

    manifest["fecha_actualizacion"] = datetime.now().isoformat(timespec="seconds")
    _guardar_manifest_carga(empresa_id, lote_id, manifest)

    flash("Se guardaron los datos de todos los documentos del lote correctamente.", "success")
    return redirect(f"/crv/carga-inteligente?lote={lote_id}")


def _actualizar_revision_masiva(empresa_id, manifest):
    for item in manifest.get("archivos", []):
        if item.get("cuenta_pagar_id"):
            continue

        archivo_id = item.get("archivo_id")
        proveedor = request.form.get(f"proveedor_{archivo_id}", "").strip()
        identificacion = request.form.get(
            f"identificacion_{archivo_id}",
            "",
        ).strip()
        numero_documento = request.form.get(
            f"numero_documento_{archivo_id}",
            "",
        ).strip()
        fecha_documento = request.form.get(
            f"fecha_documento_{archivo_id}",
            "",
        ).strip()
        base = convertir_numero(
            request.form.get(f"base_gravable_{archivo_id}"),
            None,
        )
        tarifa = convertir_porcentaje(
            request.form.get(f"tarifa_iva_{archivo_id}"),
            None,
        )
        iva = convertir_numero(
            request.form.get(f"valor_iva_{archivo_id}"),
            None,
        )
        total = convertir_numero(
            request.form.get(f"total_documento_{archivo_id}"),
            None,
        )
        tipo_iva = request.form.get(
            f"tipo_iva_{archivo_id}",
            "",
        ).strip().upper()
        tipo_documento = request.form.get(
            f"tipo_documento_tercero_{archivo_id}",
            item.get("tipo_documento_tercero", ""),
        ).strip().upper()

        tercero = _buscar_tercero_por_identificacion_carga(
            empresa_id,
            identificacion,
        )
        duplicado, observacion_duplicado = _es_factura_duplicada_carga(
            empresa_id,
            identificacion,
            numero_documento,
        )

        item.update({
            "proveedor": proveedor,
            "identificacion": identificacion,
            "tipo_documento_tercero": tipo_documento or item.get("tipo_documento_tercero", ""),
            "numero_documento": numero_documento,
            "fecha_documento": fecha_documento,
            "base_gravable": base,
            "tarifa_iva": tarifa,
            "tipo_iva": tipo_iva,
            "valor_iva": iva,
            "total_documento": total,
            "tercero_existente": bool(tercero),
            "tercero_id": tercero.id if tercero else None,
            "duplicado": duplicado,
            "revision_manual": True,
            "fecha_revision_manual": datetime.now().isoformat(timespec="seconds"),
        })

        estado, faltantes, alertas = _estado_revision_carga(item)
        item["estado"] = estado
        item["alertas_validacion"] = alertas

        observaciones = []
        if observacion_duplicado:
            observaciones.append(observacion_duplicado)
        if faltantes:
            observaciones.append("Revisar: " + ", ".join(faltantes) + ".")
        observaciones.extend(alertas)
        if not tercero and identificacion:
            observaciones.append("El tercero se creará al aprobar esta factura.")
        item["observaciones"] = " ".join(observaciones)


@crv_bp.route(
    "/carga-inteligente/<lote_id>/aprobar",
    methods=["POST"],
)
def carga_inteligente_aprobar_lote(lote_id):
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    manifest = _leer_manifest_carga(empresa_id, lote_id)
    if not manifest:
        flash("El lote no existe o venció.", "error")
        return redirect("/crv/carga-inteligente")

    if manifest.get("estado") != "PENDIENTE_REVISION":
        flash("Este lote ya fue aprobado o ya no está disponible.", "warning")
        return redirect(f"/crv/carga-inteligente?lote={lote_id}")

    for item in manifest.get("archivos", []):
        cuenta_existente = obtener_cuenta_carga_inteligente(
            empresa_id,
            lote_id,
            item.get("archivo_id"),
        )
        if cuenta_existente:
            item.update({
                "estado": "REGISTRADO",
                "cuenta_pagar_id": cuenta_existente.id,
                "tercero_id": cuenta_existente.proveedor_id,
                "tercero_existente": True,
                "observaciones": (
                    f"Cuenta por pagar #{cuenta_existente.id} ya registrada."
                ),
            })

    _actualizar_revision_masiva(empresa_id, manifest)
    pendientes = [
        item
        for item in manifest.get("archivos", [])
        if not item.get("cuenta_pagar_id")
    ]

    bloqueos = []
    for item in pendientes:
        estado, faltantes, alertas = _estado_revision_carga(item)
        item["estado"] = estado
        if estado != "LISTO_PARA_APROBAR":
            detalle = faltantes + alertas
            if item.get("duplicado"):
                detalle.append("la factura ya existe")
            bloqueos.append(
                f"{item.get('nombre_original', 'Documento')}: "
                + (", ".join(detalle) or estado)
            )
        elif (
            _buscar_tercero_por_identificacion_carga(
                empresa_id,
                item.get("identificacion"),
            )
            is None
            and item.get("tipo_documento_tercero") not in {"NIT", "CEDULA"}
        ):
            bloqueos.append(
                f"{item.get('nombre_original', 'Documento')}: "
                "selecciona NIT o cédula para el nuevo proveedor"
            )

    if not pendientes:
        manifest["estado"] = "APROBADO"
        manifest["fecha_aprobacion"] = datetime.now().isoformat(timespec="seconds")
        _guardar_manifest_carga(empresa_id, lote_id, manifest)
        flash("Las facturas de este lote ya estaban registradas.", "success")
        return redirect(f"/crv/carga-inteligente?lote={lote_id}")

    if bloqueos:
        manifest["fecha_actualizacion"] = datetime.now().isoformat(timespec="seconds")
        _guardar_manifest_carga(empresa_id, lote_id, manifest)
        flash(
            "No se registró ninguna factura. Corrige los documentos antes de aprobar: "
            + " | ".join(bloqueos),
            "error",
        )
        return redirect(f"/crv/carga-inteligente?lote={lote_id}")

    try:
        cuentas = [
            registrar_factura_carga_inteligente(
                empresa_id,
                lote_id,
                item,
            )
            for item in pendientes
        ]
        db.session.commit()
    except Exception as error:
        db.session.rollback()
        current_app.logger.exception(
            "No se pudo aprobar el lote de carga inteligente %s",
            lote_id,
        )
        flash(f"No se registró ninguna factura: {error}", "error")
        return redirect(f"/crv/carga-inteligente?lote={lote_id}")

    for item, cuenta in zip(pendientes, cuentas):
        item.update({
            "estado": "REGISTRADO",
            "cuenta_pagar_id": cuenta.id,
            "tercero_id": cuenta.proveedor_id,
            "tercero_existente": True,
            "fecha_aprobacion": datetime.now().isoformat(timespec="seconds"),
            "observaciones": (
                f"Cuenta por pagar #{cuenta.id} y movimiento de compra registrados."
            ),
        })

    manifest["estado"] = "APROBADO"
    manifest["fecha_aprobacion"] = datetime.now().isoformat(timespec="seconds")
    _guardar_manifest_carga(empresa_id, lote_id, manifest)
    flash(
        f"Se aprobaron {len(cuentas)} factura(s). Se crearon o reutilizaron sus terceros y "
        "se registraron las cuentas por pagar con sus movimientos de compra vinculados.",
        "success",
    )
    return redirect(f"/crv/carga-inteligente?lote={lote_id}")

@crv_bp.route(
    "/carga-inteligente",
    methods=["GET", "POST"]
)
def carga_inteligente():

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get(
        "empresa_id"
    )

    empresa_nombre = session.get(
        "empresa_nombre",
        "CRV CONSTRUCTORA"
    )

    if request.method == "POST":

        archivos = request.files.getlist(
            "documentos"
        )

        archivos = [
            archivo
            for archivo in archivos
            if archivo
            and str(
                archivo.filename or ""
            ).strip()
        ]

        if not archivos:

            flash(
                "Selecciona al menos una factura o documento.",
                "error"
            )

            return redirect(
                "/crv/carga-inteligente"
            )

        lote_id = (
            datetime.now().strftime(
                "%Y%m%d-%H%M%S"
            )
            + "-"
            + uuid.uuid4().hex[:8]
        )

        carpeta_lote = (
            _ruta_lote_carga(
                empresa_id,
                lote_id
            )
        )

        carpeta_lote.mkdir(
            parents=True,
            exist_ok=True
        )

        manifest = {
            "lote_id": lote_id,
            "empresa_id": int(
                empresa_id
            ),
            "empresa_nombre": (
                empresa_nombre
            ),
            "fecha_creacion": (
                datetime.now().isoformat(
                    timespec="seconds"
                )
            ),
            "usuario": str(
                session.get(
                    "usuario",
                    ""
                )
            ),
            "estado": "PENDIENTE_REVISION",
            "archivos": [],
        }

        errores = []

        for archivo in archivos:

            valido, mensaje = (
                _archivo_carga_valido(
                    archivo
                )
            )

            if not valido:

                errores.append(
                    (
                        f"{archivo.filename}: "
                        f"{mensaje}"
                    )
                )

                continue

            archivo.stream.seek(
                0,
                2
            )

            tamano = archivo.stream.tell()

            archivo.stream.seek(
                0
            )

            if (
                tamano
                > TAMANO_MAXIMO_ARCHIVO_CARGA
            ):

                errores.append(
                    (
                        f"{archivo.filename}: "
                        "supera el maximo de 25 MB."
                    )
                )

                continue

            nombre_original = str(
                archivo.filename
            ).strip()

            nombre_seguro = (
                secure_filename(
                    nombre_original
                )
                or "documento"
            )

            extension = Path(
                nombre_seguro
            ).suffix.lower()

            archivo_id = (
                uuid.uuid4().hex[:12]
            )

            nombre_guardado = (
                f"{archivo_id}"
                f"{extension}"
            )

            ruta_destino = (
                carpeta_lote
                / nombre_guardado
            )

            archivo.save(
                str(
                    ruta_destino
                )
            )

            manifest[
                "archivos"
            ].append({
                "archivo_id": archivo_id,
                "nombre_original": nombre_original,
                "nombre_guardado": nombre_guardado,
                "extension": extension,
                "tamano_bytes": tamano,
                "estado": "PENDIENTE_LECTURA",
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
                "duplicado": False,
                "observaciones": "",
            })

        if not manifest["archivos"]:

            try:
                carpeta_lote.rmdir()
            except Exception:
                pass

            flash(
                (
                    "No se pudo cargar ningun archivo. "
                    + (
                        " ".join(
                            errores
                        )
                        if errores
                        else ""
                    )
                ),
                "error"
            )

            return redirect(
                "/crv/carga-inteligente"
            )

        _guardar_manifest_carga(
            empresa_id,
            lote_id,
            manifest
        )

        flash(
            (
                f"Lote creado con "
                f"{len(manifest['archivos'])} "
                "documento(s). "
                "Aun no se ha creado ningun movimiento."
            ),
            "success"
        )

        if errores:
            flash(
                "Algunos archivos no se cargaron: "
                + " ".join(
                    errores
                ),
                "warning"
            )

        return redirect(
            (
                "/crv/carga-inteligente"
                f"?lote={lote_id}"
            )
        )

    lote_actual_id = request.args.get(
        "lote",
        ""
    ).strip()

    lote_actual = None

    if lote_actual_id:
        lote_actual = (
            _leer_manifest_carga(
                empresa_id,
                lote_actual_id
            )
        )

    lotes = (
        _listar_lotes_carga_inteligente(
            empresa_id
        )
    )

    return render_template(
        "contabilidad/crv_carga_inteligente.html",
        empresa_nombre=empresa_nombre,
        lote=lote_actual,
        lotes=lotes
    )

@crv_bp.route(
    "/carga-inteligente/<lote_id>/archivo/<archivo_id>/revisar",
    methods=["POST"]
)
def carga_inteligente_revisar_archivo(lote_id, archivo_id):
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    manifest = _leer_manifest_carga(empresa_id, lote_id)

    if not manifest:
        flash("El lote solicitado no existe.", "error")
        return redirect("/crv/carga-inteligente")

    if manifest.get("estado") != "PENDIENTE_REVISION":
        flash("Este lote ya no puede modificarse.", "warning")
        return redirect(f"/crv/carga-inteligente?lote={lote_id}")

    item = next(
        (
            fila for fila in manifest.get("archivos", [])
            if str(fila.get("archivo_id", "")) == str(archivo_id)
        ),
        None
    )

    if not item:
        flash("El documento no existe dentro del lote.", "error")
        return redirect(f"/crv/carga-inteligente?lote={lote_id}")

    proveedor = request.form.get("proveedor", "").strip()
    identificacion = request.form.get("identificacion", "").strip()
    numero_documento = request.form.get("numero_documento", "").strip()
    fecha_documento = request.form.get("fecha_documento", "").strip()

    base = convertir_numero(request.form.get("base_gravable"), None)
    tarifa = convertir_porcentaje(request.form.get("tarifa_iva"), None)
    iva = convertir_numero(request.form.get("valor_iva"), None)
    total = convertir_numero(request.form.get("total_documento"), None)

    # Fecha debe quedar en ISO YYYY-MM-DD o vacía.
    if fecha_documento and not convertir_fecha(fecha_documento):
        flash("La fecha del documento no es válida.", "error")
        return redirect(f"/crv/carga-inteligente?lote={lote_id}")

    tercero = _buscar_tercero_por_identificacion_carga(
        empresa_id,
        identificacion
    )

    duplicado, observacion_duplicado = _es_factura_duplicada_carga(
        empresa_id,
        identificacion,
        numero_documento
    )

    item.update({
        "proveedor": proveedor,
        "identificacion": identificacion,
        "numero_documento": numero_documento,
        "fecha_documento": fecha_documento,
        "base_gravable": base,
        "tarifa_iva": tarifa,
        "valor_iva": iva,
        "total_documento": total,
        "tercero_existente": bool(tercero),
        "tercero_id": tercero.id if tercero else None,
        "duplicado": duplicado,
        "revision_manual": True,
        "fecha_revision_manual": datetime.now().isoformat(timespec="seconds"),
    })

    estado, faltantes, alertas = _estado_revision_carga(item)
    item["estado"] = estado
    item["alertas_validacion"] = alertas

    observaciones = []
    if observacion_duplicado:
        observaciones.append(observacion_duplicado)
    if faltantes:
        observaciones.append("Revisar: " + ", ".join(faltantes) + ".")
    observaciones.extend(alertas)
    if not tercero and identificacion:
        observaciones.append("El NIT no existe todavía en Terceros.")

    item["observaciones"] = " ".join(observaciones)

    _guardar_manifest_carga(empresa_id, lote_id, manifest)

    if estado == "LISTO_PARA_APROBAR":
        flash(
            "Revisión guardada. Los datos cuadran y el documento queda listo para una futura aprobación.",
            "success"
        )
    elif estado == "POSIBLE_DUPLICADO":
        flash(
            "Revisión guardada, pero el documento sigue marcado como posible duplicado.",
            "warning"
        )
    else:
        flash(
            "Revisión guardada. Aún hay campos o valores que deben corregirse.",
            "warning"
        )

    return redirect(f"/crv/carga-inteligente?lote={lote_id}")

@crv_bp.route(
    "/carga-inteligente/<lote_id>/archivo/<archivo_id>/ver",
    methods=["GET"],
)
def carga_inteligente_ver_archivo(lote_id, archivo_id):
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    manifest = _leer_manifest_carga(empresa_id, lote_id)

    if (
        not manifest
        or manifest.get("estado") != "APROBADO"
        or str(manifest.get("empresa_id")) != str(empresa_id)
    ):
        return "Documento no encontrado.", 404

    item = next(
        (
            fila for fila in manifest.get("archivos", [])
            if str(fila.get("archivo_id", "")) == str(archivo_id)
        ),
        None,
    )
    if not item:
        return "Documento no encontrado.", 404

    nombre_guardado = str(item.get("nombre_guardado") or "")
    extension = Path(nombre_guardado).suffix.lower()
    extensiones_permitidas = {
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
    }
    if (
        not nombre_guardado
        or nombre_guardado != Path(nombre_guardado).name
        or "\\" in nombre_guardado
        or extension not in extensiones_permitidas
    ):
        return "Documento no encontrado.", 404

    carpeta = _ruta_lote_carga(empresa_id, lote_id)
    if not carpeta:
        return "Documento no encontrado.", 404

    ruta_archivo = (carpeta / nombre_guardado).resolve()
    if (
        ruta_archivo.parent != carpeta.resolve()
        or not ruta_archivo.is_file()
    ):
        return "Documento no encontrado.", 404

    tipos_mime = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    respuesta = send_file(
        ruta_archivo,
        mimetype=tipos_mime[extension],
        as_attachment=False,
        download_name=Path(
            str(item.get("nombre_original") or "documento")
        ).name,
    )
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    return respuesta

@crv_bp.route(
    "/carga-inteligente/<lote_id>/archivo/<archivo_id>/eliminar",
    methods=["POST"]
)
def carga_inteligente_eliminar_archivo(
    lote_id,
    archivo_id
):

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get(
        "empresa_id"
    )

    manifest = (
        _leer_manifest_carga(
            empresa_id,
            lote_id
        )
    )

    if not manifest:

        flash(
            "El lote solicitado no existe.",
            "error"
        )

        return redirect(
            "/crv/carga-inteligente"
        )

    if (
        manifest.get("estado")
        != "PENDIENTE_REVISION"
    ):

        flash(
            "Este lote ya no puede modificarse.",
            "warning"
        )

        return redirect(
            (
                "/crv/carga-inteligente"
                f"?lote={lote_id}"
            )
        )

    carpeta = _ruta_lote_carga(
        empresa_id,
        lote_id
    )

    nuevos_archivos = []
    eliminado = False

    for item in manifest.get(
        "archivos",
        []
    ):

        if (
            str(
                item.get(
                    "archivo_id",
                    ""
                )
            )
            == str(
                archivo_id
            )
        ):

            ruta = (
                carpeta
                / str(
                    item.get(
                        "nombre_guardado",
                        ""
                    )
                )
            )

            if ruta.exists():

                try:
                    ruta.unlink()
                except Exception:
                    pass

            eliminado = True
            continue

        nuevos_archivos.append(
            item
        )

    manifest[
        "archivos"
    ] = nuevos_archivos

    _guardar_manifest_carga(
        empresa_id,
        lote_id,
        manifest
    )

    if eliminado:

        flash(
            "Documento retirado del lote.",
            "success"
        )

    return redirect(
        (
            "/crv/carga-inteligente"
            f"?lote={lote_id}"
        )
    )

@crv_bp.route(
    "/carga-inteligente/<lote_id>/eliminar",
    methods=["POST"]
)
def carga_inteligente_eliminar_lote(
    lote_id
):

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get(
        "empresa_id"
    )

    manifest = (
        _leer_manifest_carga(
            empresa_id,
            lote_id
        )
    )

    if not manifest:

        return redirect(
            "/crv/carga-inteligente"
        )

    if (
        manifest.get("estado")
        != "PENDIENTE_REVISION"
    ):

        flash(
            "Solo se pueden eliminar lotes pendientes.",
            "warning"
        )

        return redirect(
            (
                "/crv/carga-inteligente"
                f"?lote={lote_id}"
            )
        )

    carpeta = _ruta_lote_carga(
        empresa_id,
        lote_id
    )

    try:
        for archivo in carpeta.iterdir():
            if archivo.is_file():
                archivo.unlink()

        carpeta.rmdir()

        flash(
            "Lote pendiente eliminado correctamente.",
            "success"
        )

    except Exception as error:

        flash(
            (
                "No fue posible eliminar el lote: "
                f"{error}"
            ),
            "error"
        )

    return redirect(
        "/crv/carga-inteligente"
    )

__all__ = ['carga_inteligente_procesar', 'carga_inteligente_guardar_masivo', 'carga_inteligente', 'carga_inteligente_revisar_archivo', 'carga_inteligente_eliminar_archivo', 'carga_inteligente_eliminar_lote']
