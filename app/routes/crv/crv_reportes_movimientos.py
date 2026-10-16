"""CRV report routes: movimientos."""

from .crv_core import (
    A4,
    BytesIO,
    CRVMovimiento,
    Image,
    Paragraph,
    ParagraphStyle,
    Path,
    SimpleDocTemplate,
    Spacer,
    TA_CENTER,
    Table,
    TableStyle,
    Workbook,
    _enviar_excel,
    _enviar_pdf,
    _excel_auto_ancho,
    _excel_encabezado,
    _excel_moneda,
    _excel_titulo,
    _money_export,
    _pdf_encabezado_historia,
    _pdf_tabla,
    _texto_pdf_seguro,
    _tipo_comprobante_movimiento,
    _titulo_comprobante_por_prefijo,
    colors,
    crv_bp,
    current_app,
    date,
    db,
    getSampleStyleSheet,
    get_column_letter,
    mm,
    proteger_crv,
    request,
    send_file,
    session,
)

@crv_bp.route("/movimientos/excel")
def movimientos_excel():

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    mes = request.args.get(
        "mes",
        ""
    ).strip()

    query = CRVMovimiento.query.filter_by(
        empresa_id=empresa_id
    )

    if mes:
        try:
            anio, numero_mes = mes.split("-")
            query = query.filter(
                db.extract(
                    "year",
                    CRVMovimiento.fecha
                ) == int(anio),
                db.extract(
                    "month",
                    CRVMovimiento.fecha
                ) == int(numero_mes)
            )
        except ValueError:
            pass

    movimientos = query.order_by(
        CRVMovimiento.fecha.asc(),
        CRVMovimiento.id.asc()
    ).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "MOVIMIENTOS"

    headers = [
        "Fecha",
        "Tipo",
        "Categoría",
        "Subcategoría",
        "Tercero",
        "NIT/ID",
        "Documento",
        "Concepto",
        "Descripción",
        "Cuenta origen CRV",
        "Cuenta destino / beneficiario",
        "Proyecto",
        "Centro costo",
        "Obra",
        "Base gravable",
        "Tipo IVA",
        "Tarifa IVA %",
        "Valor IVA",
        "Total documento",
        "Descuento",
        "Retención",
        "Otros descuentos",
        "Valor neto",
        "Forma pago",
        "Soporte",
        "Referencia",
        "Revisado"
    ]

    _excel_titulo(
        ws,
        "CRV CONSTRUCTORA - MOVIMIENTOS",
        (
            f"Periodo: {mes}"
            if mes
            else "Todos los registros"
        ),
        len(headers)
    )

    _excel_encabezado(
        ws,
        4,
        headers
    )

    for fila, m in enumerate(
        movimientos,
        5
    ):
        valores = [
            m.fecha,
            m.tipo,
            m.categoria,
            m.subcategoria,
            m.nombre_tercero,
            m.tercero_identificacion,
            m.numero_documento,
            m.concepto,
            m.descripcion,
            m.cuenta,
            m.cuenta_destino,
            m.proyecto,
            m.centro_costo,
            m.obra,
            float(m.base_gravable or 0),
            m.tipo_iva or "NO_APLICA",
            float(m.tarifa_iva or 0),
            float(m.valor_iva or 0),
            float(m.valor or 0),
            float(m.descuento or 0),
            float(m.retencion or 0),
            float(m.otros_descuentos or 0),
            float(
                m.valor_neto
                or m.valor
                or 0
            ),
            m.forma_pago,
            m.numero_soporte,
            m.referencia_pago,
            "SI" if m.revisado else "NO"
        ]

        for col, valor in enumerate(
            valores,
            1
        ):
            ws.cell(
                fila,
                col,
                valor
            )

        for col in range(
            15,
            20
        ):
            _excel_moneda(
                ws.cell(
                    fila,
                    col
                )
            )

    ws.freeze_panes = "A5"
    ws.auto_filter.ref = (
        f"A4:"
        f"{get_column_letter(len(headers))}"
        f"{max(4, ws.max_row)}"
    )

    _excel_auto_ancho(ws)

    return _enviar_excel(
        wb,
        (
            f"CRV_movimientos_"
            f"{date.today().isoformat()}.xlsx"
        )
    )


@crv_bp.route(
    "/movimientos/<int:movimiento_id>/comprobante-pdf"
)
def movimiento_comprobante_pdf(movimiento_id):

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

    movimiento = (
        CRVMovimiento.query
        .filter_by(
            id=movimiento_id,
            empresa_id=empresa_id
        )
        .first_or_404()
    )

    prefijo = str(
        movimiento.comprobante_tipo
        or ""
    ).strip().upper()

    consecutivo = str(
        movimiento.comprobante_codigo
        or ""
    ).strip().upper()

    # La migracion y las rutas de registro asignan el consecutivo.
    # Abrir el PDF no crea ni modifica numeracion.
    if not prefijo or not consecutivo:
        titulo_calculado, prefijo_calculado = (
            _tipo_comprobante_movimiento(
                movimiento
            )
        )

        prefijo = (
            prefijo
            or prefijo_calculado
        )

        titulo_comprobante = (
            _titulo_comprobante_por_prefijo(
                prefijo
            )
        )

        consecutivo = (
            consecutivo
            or "SIN-CONSECUTIVO"
        )
    else:
        titulo_comprobante = (
            _titulo_comprobante_por_prefijo(
                prefijo
            )
        )

    def dinero(valor):
        return (
            f"$"
            f"{float(valor or 0):,.0f}"
        )

    def fecha_texto(valor):
        if not valor:
            return "-"

        try:
            return valor.strftime(
                "%d/%m/%Y"
            )
        except Exception:
            return str(valor)

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=12 * mm,
        bottomMargin=14 * mm,
        title=(
            f"{titulo_comprobante} "
            f"{consecutivo}"
        ),
        author=empresa_nombre
    )

    styles = getSampleStyleSheet()

    titulo_style = ParagraphStyle(
        "ComprobanteTitulo",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=19,
        textColor=colors.HexColor(
            "#17304F"
        ),
        alignment=TA_CENTER,
        spaceAfter=3
    )

    subtitulo_style = ParagraphStyle(
        "ComprobanteSubtitulo",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor(
            "#667085"
        ),
        alignment=TA_CENTER
    )

    label_style = ParagraphStyle(
        "ComprobanteLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.2,
        leading=9,
        textColor=colors.HexColor(
            "#17304F"
        )
    )

    value_style = ParagraphStyle(
        "ComprobanteValue",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor(
            "#25364A"
        )
    )

    value_bold_style = ParagraphStyle(
        "ComprobanteValueBold",
        parent=value_style,
        fontName="Helvetica-Bold"
    )

    obs_style = ParagraphStyle(
        "ComprobanteObs",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor(
            "#25364A"
        )
    )

    story = []

    logo_path = (
        Path(current_app.root_path)
        / "static"
        / "logo_crv.png"
    )

    if logo_path.exists():
        story.append(
            Image(
                str(logo_path),
                width=25 * mm,
                height=19 * mm
            )
        )

    story.append(
        Paragraph(
            _texto_pdf_seguro(
                empresa_nombre
            ),
            titulo_style
        )
    )

    story.append(
        Paragraph(
            titulo_comprobante,
            titulo_style
        )
    )

    story.append(
        Paragraph(
            (
                f"Consecutivo: <b>{consecutivo}</b>"
                f" &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"Fecha contable: "
                f"<b>{fecha_texto(movimiento.fecha)}</b>"
            ),
            subtitulo_style
        )
    )

    story.append(
        Spacer(
            1,
            5 * mm
        )
    )

    # --------------------------------------------------------
    # IDENTIFICACIÓN DEL TERCERO Y DOCUMENTO
    # --------------------------------------------------------

    tercero_nombre = (
        movimiento.nombre_tercero
        or movimiento.tercero_nombre
        or movimiento.beneficiario
        or "-"
    )

    identificacion = (
        movimiento.tercero_identificacion
        or "-"
    )

    documento = (
        movimiento.numero_documento
        or movimiento.numero_soporte
        or "-"
    )

    tipo_documento = (
        movimiento.tipo_documento
        or "-"
    )

    datos_generales = [
        [
            Paragraph(
                "Tercero / beneficiario",
                label_style
            ),
            Paragraph(
                _texto_pdf_seguro(
                    tercero_nombre
                ),
                value_bold_style
            ),
            Paragraph(
                "NIT / Identificación",
                label_style
            ),
            Paragraph(
                _texto_pdf_seguro(
                    identificacion
                ),
                value_style
            ),
        ],
        [
            Paragraph(
                "Tipo de documento",
                label_style
            ),
            Paragraph(
                _texto_pdf_seguro(
                    tipo_documento
                ),
                value_style
            ),
            Paragraph(
                "Documento / soporte",
                label_style
            ),
            Paragraph(
                _texto_pdf_seguro(
                    documento
                ),
                value_style
            ),
        ],
        [
            Paragraph(
                "Fecha documento",
                label_style
            ),
            Paragraph(
                fecha_texto(
                    movimiento.fecha_documento
                ),
                value_style
            ),
            Paragraph(
                "Fecha vencimiento",
                label_style
            ),
            Paragraph(
                fecha_texto(
                    movimiento.fecha_vencimiento
                ),
                value_style
            ),
        ],
    ]

    tabla_generales = Table(
        datos_generales,
        colWidths=[
            34 * mm,
            58 * mm,
            34 * mm,
            49 * mm
        ]
    )

    tabla_generales.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.HexColor("#EEF3F8")
            ),
            (
                "BACKGROUND",
                (2, 0),
                (2, -1),
                colors.HexColor("#EEF3F8")
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.4,
                colors.HexColor("#D9E1E8")
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                6
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                6
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                6
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                6
            ),
        ])
    )

    story.append(
        tabla_generales
    )

    story.append(
        Spacer(
            1,
            4 * mm
        )
    )

    # --------------------------------------------------------
    # CONCEPTO / CLASIFICACIÓN
    # --------------------------------------------------------

    clasificacion = [
        [
            Paragraph(
                "Tipo",
                label_style
            ),
            Paragraph(
                _texto_pdf_seguro(
                    movimiento.tipo
                ),
                value_style
            ),
            Paragraph(
                "Categoría",
                label_style
            ),
            Paragraph(
                _texto_pdf_seguro(
                    movimiento.categoria
                ),
                value_style
            ),
        ],
        [
            Paragraph(
                "Concepto",
                label_style
            ),
            Paragraph(
                _texto_pdf_seguro(
                    movimiento.concepto
                ),
                value_bold_style
            ),
            Paragraph(
                "Subcategoría",
                label_style
            ),
            Paragraph(
                _texto_pdf_seguro(
                    movimiento.subcategoria
                ),
                value_style
            ),
        ],
        [
            Paragraph(
                "Proyecto",
                label_style
            ),
            Paragraph(
                _texto_pdf_seguro(
                    movimiento.proyecto
                ),
                value_style
            ),
            Paragraph(
                "Centro de costo",
                label_style
            ),
            Paragraph(
                _texto_pdf_seguro(
                    movimiento.centro_costo
                ),
                value_style
            ),
        ],
        [
            Paragraph(
                "Obra / frente",
                label_style
            ),
            Paragraph(
                _texto_pdf_seguro(
                    movimiento.obra
                ),
                value_style
            ),
            Paragraph(
                "Origen del registro",
                label_style
            ),
            Paragraph(
                _texto_pdf_seguro(
                    movimiento.origen_registro
                ),
                value_style
            ),
        ],
    ]

    tabla_clasificacion = Table(
        clasificacion,
        colWidths=[
            27 * mm,
            65 * mm,
            30 * mm,
            53 * mm
        ]
    )

    tabla_clasificacion.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.HexColor("#FFF7DB")
            ),
            (
                "BACKGROUND",
                (2, 0),
                (2, -1),
                colors.HexColor("#FFF7DB")
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.4,
                colors.HexColor("#D9E1E8")
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP"
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                6
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                6
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                6
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                6
            ),
        ])
    )

    story.append(
        tabla_clasificacion
    )

    story.append(
        Spacer(
            1,
            4 * mm
        )
    )

    # --------------------------------------------------------
    # VALORES / IVA
    # --------------------------------------------------------

    total_documento = float(
        movimiento.valor or 0
    )

    valor_neto = float(
        movimiento.valor_neto
        or movimiento.valor
        or 0
    )

    total_descuentos = (
        float(movimiento.descuento or 0)
        + float(movimiento.retencion or 0)
        + float(
            movimiento.otros_descuentos
            or 0
        )
    )

    iva_detalle = (
        f"{float(movimiento.tarifa_iva or 0):g}%"
        f" · "
        f"{_texto_pdf_seguro(movimiento.tipo_iva or 'NO_APLICA')}"
    )

    valores = [
        [
            "Base gravable",
            dinero(
                movimiento.base_gravable
            ),
            "IVA",
            dinero(
                movimiento.valor_iva
            ),
        ],
        [
            "Tratamiento IVA",
            iva_detalle,
            "Total documento",
            dinero(
                total_documento
            ),
        ],
        [
            "Descuento",
            dinero(
                movimiento.descuento
            ),
            "Retención",
            dinero(
                movimiento.retencion
            ),
        ],
        [
            "Otros descuentos",
            dinero(
                movimiento.otros_descuentos
            ),
            "Total descuentos",
            dinero(
                total_descuentos
            ),
        ],
        [
            "VALOR NETO",
            dinero(
                valor_neto
            ),
            "",
            "",
        ],
    ]

    datos_valores = []

    for fila in valores:
        datos_valores.append([
            Paragraph(
                str(fila[0]),
                label_style
            ),
            Paragraph(
                str(fila[1]),
                (
                    value_bold_style
                    if fila[0] == "VALOR NETO"
                    else value_style
                )
            ),
            Paragraph(
                str(fila[2]),
                label_style
            ),
            Paragraph(
                str(fila[3]),
                value_style
            ),
        ])

    tabla_valores = Table(
        datos_valores,
        colWidths=[
            34 * mm,
            53 * mm,
            34 * mm,
            54 * mm
        ]
    )

    tabla_valores.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (0, -2),
                colors.HexColor("#EEF3F8")
            ),
            (
                "BACKGROUND",
                (2, 0),
                (2, -2),
                colors.HexColor("#EEF3F8")
            ),
            (
                "BACKGROUND",
                (0, -1),
                (1, -1),
                colors.HexColor("#FFF4C7")
            ),
            (
                "SPAN",
                (1, -1),
                (3, -1)
            ),
            (
                "GRID",
                (0, 0),
                (-1, -2),
                0.4,
                colors.HexColor("#D9E1E8")
            ),
            (
                "BOX",
                (0, -1),
                (3, -1),
                0.6,
                colors.HexColor("#D8B541")
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                6
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                6
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                6
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                6
            ),
        ])
    )

    story.append(
        tabla_valores
    )

    story.append(
        Spacer(
            1,
            4 * mm
        )
    )

    # --------------------------------------------------------
    # PAGO / CUENTAS
    # --------------------------------------------------------

    pago = [
        [
            Paragraph(
                "Forma de pago",
                label_style
            ),
            Paragraph(
                _texto_pdf_seguro(
                    movimiento.forma_pago
                ),
                value_style
            ),
            Paragraph(
                "Cuenta CRV",
                label_style
            ),
            Paragraph(
                _texto_pdf_seguro(
                    movimiento.cuenta
                ),
                value_style
            ),
        ],
        [
            Paragraph(
                "Cuenta destino",
                label_style
            ),
            Paragraph(
                _texto_pdf_seguro(
                    movimiento.cuenta_destino
                ),
                value_style
            ),
            Paragraph(
                "Beneficiario",
                label_style
            ),
            Paragraph(
                _texto_pdf_seguro(
                    movimiento.beneficiario
                    or tercero_nombre
                ),
                value_style
            ),
        ],
        [
            Paragraph(
                "Referencia",
                label_style
            ),
            Paragraph(
                _texto_pdf_seguro(
                    movimiento.referencia_pago
                ),
                value_style
            ),
            Paragraph(
                "Soporte",
                label_style
            ),
            Paragraph(
                _texto_pdf_seguro(
                    movimiento.numero_soporte
                ),
                value_style
            ),
        ],
    ]

    tabla_pago = Table(
        pago,
        colWidths=[
            31 * mm,
            56 * mm,
            31 * mm,
            57 * mm
        ]
    )

    tabla_pago.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.HexColor("#EEF3F8")
            ),
            (
                "BACKGROUND",
                (2, 0),
                (2, -1),
                colors.HexColor("#EEF3F8")
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.4,
                colors.HexColor("#D9E1E8")
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                6
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                6
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                6
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                6
            ),
        ])
    )

    story.append(
        tabla_pago
    )

    # --------------------------------------------------------
    # DESCRIPCIÓN Y OBSERVACIONES
    # --------------------------------------------------------

    descripcion = str(
        movimiento.descripcion
        or ""
    ).strip()

    observaciones = str(
        movimiento.observaciones
        or ""
    ).strip()

    if descripcion:
        story.append(
            Spacer(
                1,
                4 * mm
            )
        )

        story.append(
            Paragraph(
                "<b>Descripción:</b> "
                + _texto_pdf_seguro(
                    descripcion
                ),
                obs_style
            )
        )

    if observaciones:
        story.append(
            Spacer(
                1,
                2 * mm
            )
        )

        story.append(
            Paragraph(
                "<b>Observaciones:</b> "
                + _texto_pdf_seguro(
                    observaciones
                ),
                obs_style
            )
        )

    # --------------------------------------------------------
    # FIRMAS
    # --------------------------------------------------------

    story.append(
        Spacer(
            1,
            13 * mm
        )
    )

    firmas = Table(
        [
            [
                "____________________________",
                "____________________________",
                "____________________________",
            ],
            [
                "Elaborado por",
                "Revisado por",
                (
                    "Recibido por"
                    if titulo_comprobante
                    == "COMPROBANTE DE EGRESO"
                    else "Responsable"
                ),
            ],
            [
                _texto_pdf_seguro(
                    movimiento.usuario_registro
                    or session.get(
                        "usuario",
                        ""
                    )
                ),
                "",
                "",
            ],
        ],
        colWidths=[
            58 * mm,
            58 * mm,
            58 * mm
        ]
    )

    firmas.setStyle(
        TableStyle([
            (
                "ALIGN",
                (0, 0),
                (-1, -1),
                "CENTER"
            ),
            (
                "FONTNAME",
                (0, 1),
                (-1, 1),
                "Helvetica-Bold"
            ),
            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                7.5
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, -1),
                colors.HexColor("#25364A")
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                2
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                2
            ),
        ])
    )

    story.append(
        firmas
    )

    def pie_pagina(
        canvas,
        doc_obj
    ):
        canvas.saveState()

        ancho, _ = A4

        canvas.setStrokeColor(
            colors.HexColor(
                "#D8B541"
            )
        )

        canvas.setLineWidth(
            0.8
        )

        canvas.line(
            15 * mm,
            10 * mm,
            ancho - 15 * mm,
            10 * mm
        )

        canvas.setFont(
            "Helvetica",
            6.5
        )

        canvas.setFillColor(
            colors.HexColor(
                "#667085"
            )
        )

        canvas.drawString(
            15 * mm,
            6.5 * mm,
            (
                "Documento interno generado por "
                "el sistema contable de CRV."
            )
        )

        canvas.drawRightString(
            ancho - 15 * mm,
            6.5 * mm,
            (
                f"{consecutivo} · "
                f"Página {doc_obj.page}"
            )
        )

        canvas.restoreState()

    doc.build(
        story,
        onFirstPage=pie_pagina,
        onLaterPages=pie_pagina
    )

    buffer.seek(
        0
    )

    nombre_archivo = (
        f"{consecutivo}_"
        f"{date.today().isoformat()}.pdf"
    )

    return send_file(
        buffer,
        as_attachment=False,
        download_name=nombre_archivo,
        mimetype="application/pdf"
    )


@crv_bp.route("/movimientos/pdf")
def movimientos_pdf():

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    movimientos = (
        CRVMovimiento.query
        .filter_by(
            empresa_id=empresa_id
        )
        .order_by(
            CRVMovimiento.fecha.asc(),
            CRVMovimiento.id.asc()
        )
        .all()
    )

    filas = []

    for m in movimientos:
        filas.append([
            (
                m.fecha.strftime("%d/%m/%Y")
                if m.fecha
                else ""
            ),
            m.tipo or "",
            m.nombre_tercero or "",
            m.numero_documento or "",
            m.concepto or "",
            m.cuenta or "",
            m.proyecto or "",
            _money_export(
                m.valor_neto
                or m.valor
                or 0
            )
        ])

    story = []

    _pdf_encabezado_historia(
        story,
        "CRV CONSTRUCTORA - MOVIMIENTOS",
        (
            "Listado general de movimientos contables · "
            f"Generado {date.today().strftime('%d/%m/%Y')}"
        )
    )

    story.append(
        _pdf_tabla(
            [
                "Fecha",
                "Tipo",
                "Tercero",
                "Documento",
                "Concepto",
                "Cuenta",
                "Proyecto",
                "Valor"
            ],
            filas,
            [
                20 * mm,
                28 * mm,
                42 * mm,
                26 * mm,
                48 * mm,
                35 * mm,
                32 * mm,
                26 * mm
            ]
        )
    )

    return _enviar_pdf(
        story,
        (
            f"CRV_movimientos_"
            f"{date.today().isoformat()}.pdf"
        )
    )


__all__ = ['movimiento_comprobante_pdf', 'movimientos_excel', 'movimientos_pdf']
