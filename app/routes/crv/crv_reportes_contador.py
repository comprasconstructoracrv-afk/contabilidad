"""CRV report routes: contador."""

from .crv_core import (
    A4,
    Alignment,
    BytesIO,
    CRVMovimiento,
    Font,
    Image,
    PageBreak,
    Paragraph,
    ParagraphStyle,
    Path,
    PatternFill,
    Side,
    SimpleDocTemplate,
    Spacer,
    TA_CENTER,
    TA_LEFT,
    Table,
    TableStyle,
    Workbook,
    _datos_reportes_crv,
    _periodo_texto,
    _reporte_filtros,
    colors,
    crv_bp,
    current_app,
    date,
    db,
    getSampleStyleSheet,
    get_column_letter,
    landscape,
    mm,
    proteger_crv,
    render_template,
    send_file,
    session,
)

@crv_bp.route("/reportes-contador/pdf")
def reportes_contador_pdf():
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "CRV CONSTRUCTORA")
    filtros = _reporte_filtros()
    datos = _datos_reportes_crv(empresa_id, filtros)
    resumen = datos["resumen"]

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title="Reporte contable CRV"
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CRVTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=18, leading=21, textColor=colors.HexColor("#17304F"), alignment=TA_CENTER
    )
    subtitle_style = ParagraphStyle(
        "CRVSub", parent=styles["Normal"], fontName="Helvetica",
        fontSize=8.5, leading=11, textColor=colors.HexColor("#667085"), alignment=TA_CENTER
    )
    section_style = ParagraphStyle(
        "CRVSection", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=12, leading=14, textColor=colors.HexColor("#17304F"), spaceBefore=5, spaceAfter=7
    )
    small = ParagraphStyle(
        "CRVSmall", parent=styles["Normal"], fontName="Helvetica",
        fontSize=6.5, leading=8, textColor=colors.HexColor("#25364A"), alignment=TA_LEFT
    )

    story = []
    logo_path = Path(current_app.root_path) / "static" / "logo_crv.png"
    if logo_path.exists():
        story.append(Image(str(logo_path), width=24 * mm, height=18 * mm))
    story.append(Paragraph(f"{empresa_nombre} - REPORTE CONTABLE", title_style))
    story.append(Paragraph(f"Periodo: {_periodo_texto(filtros)} · Generado: {date.today().strftime('%d/%m/%Y')}", subtitle_style))
    story.append(Spacer(1, 5 * mm))

    def money(v):
        return f"${float(v or 0):,.0f}"

    # KPI summary
    kpi_data = [
        ["Ingresos", "Compras", "Gastos", "Resultado", "CxP pendiente", "CxP vencido"],
        [
            money(resumen["ingresos"]), money(resumen["compras"]), money(resumen["gastos"]),
            money(resumen["resultado"]), money(resumen["cxp_pendiente"]), money(resumen["cxp_vencido"])
        ]
    ]
    kpi = Table(kpi_data, colWidths=[43 * mm] * 6, rowHeights=[8 * mm, 11 * mm])
    kpi.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17304F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, 1), 11),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F7F9FC")),
        ("BOX", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9E1E8")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E4EAF0")),
    ]))
    story.append(kpi)
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("Resumen de IVA", section_style))
    iva_tabla = Table(
        [
            [
                "Base IVA generado",
                "Base IVA descontable",
                "Base exenta",
                "Base excluida",
            ],
            [
                money(datos["iva_resumen"]["base_generado"]),
                money(datos["iva_resumen"]["base_descontable"]),
                money(datos["iva_resumen"]["base_exenta"]),
                money(datos["iva_resumen"]["base_excluida"]),
            ],
            [
                "IVA generado",
                "IVA descontable",
                "IVA mayor valor costo/gasto",
                "Saldo IVA preliminar",
            ],
            [
                money(datos["iva_resumen"]["iva_generado"]),
                money(datos["iva_resumen"]["iva_descontable"]),
                money(datos["iva_resumen"]["iva_mayor_valor"]),
                money(datos["iva_resumen"]["saldo_iva_preliminar"]),
            ],
        ],
        colWidths=[62 * mm] * 4
    )
    iva_tabla.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#D8B541")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor("#17304F")),
        ("FONTNAME", (0,0), (-1,-1), "Helvetica-Bold"),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#D9E1E8")),
        ("BACKGROUND", (0,1), (-1,1), colors.HexColor("#FFF9E6")),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(iva_tabla)
    story.append(Spacer(1, 5 * mm))

    # CxP summary by provider
    story.append(Paragraph("Resumen por proveedor", section_style))
    prov_rows = [["Proveedor", "NIT/ID", "Facturado", "Pagado", "Saldo", "Vencido"]]
    for p in datos["proveedores_resumen"]:
        prov_rows.append([
            Paragraph(p["nombre"], small), p["identificacion"], money(p["facturado"]),
            money(p["pagado"]), money(p["saldo"]), money(p["vencido"])
        ])
    if len(prov_rows) == 1:
        prov_rows.append(["Sin registros", "", "-", "-", "-", "-"])
    prov_table = Table(prov_rows, repeatRows=1, colWidths=[68*mm, 30*mm, 35*mm, 35*mm, 35*mm, 35*mm])
    prov_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#17304F")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 6.5),
        ("ALIGN", (2,1), (-1,-1), "RIGHT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#D9E1E8")),
        ("LEFTPADDING", (0,0), (-1,-1), 4), ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(prov_table)
    story.append(PageBreak())

    # Movements detail
    story.append(Paragraph("Listado general de movimientos", section_style))
    mov_rows = [["Fecha", "Tipo", "Tercero", "Documento", "Concepto", "Cuenta", "Proyecto", "C. costo", "Neto"]]
    for m in datos["movimientos"]:
        mov_rows.append([
            m.fecha.strftime("%d/%m/%Y") if m.fecha else "",
            Paragraph(str(m.tipo or ""), small),
            Paragraph(str(m.nombre_tercero or ""), small),
            Paragraph(str(m.numero_documento or ""), small),
            Paragraph(str(m.concepto or ""), small),
            Paragraph(str(m.cuenta or ""), small),
            Paragraph(str(m.proyecto or ""), small),
            Paragraph(str(m.centro_costo or ""), small),
            money(m.valor_neto or m.valor or 0),
        ])
    if len(mov_rows) == 1:
        mov_rows.append(["", "Sin movimientos", "", "", "", "", "", "", "-"])
    mov_table = Table(mov_rows, repeatRows=1, colWidths=[19*mm, 25*mm, 40*mm, 24*mm, 45*mm, 27*mm, 27*mm, 27*mm, 26*mm])
    mov_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#17304F")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 6),
        ("ALIGN", (-1,1), (-1,-1), "RIGHT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#D9E1E8")),
        ("LEFTPADDING", (0,0), (-1,-1), 3), ("RIGHTPADDING", (0,0), (-1,-1), 3),
        ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    story.append(mov_table)
    story.append(PageBreak())

    # CxP detail
    story.append(Paragraph("Detalle de cuentas por pagar", section_style))
    cxp_rows = [["Fecha", "Proveedor", "Documento", "Vence", "Neto", "Pagado", "Saldo", "Estado"]]
    for cta in datos["cuentas"]:
        prov = cta.proveedor
        cxp_rows.append([
            cta.fecha_documento.strftime("%d/%m/%Y") if cta.fecha_documento else "",
            Paragraph(prov.razon_social if prov else "", small),
            Paragraph(str(cta.numero_documento or ""), small),
            cta.fecha_vencimiento.strftime("%d/%m/%Y") if cta.fecha_vencimiento else "",
            money(cta.valor_neto), money(cta.total_pagado), money(cta.saldo_pendiente), cta.estado
        ])
    if len(cxp_rows) == 1:
        cxp_rows.append(["", "Sin cuentas por pagar", "", "", "-", "-", "-", ""])
    cxp_table = Table(cxp_rows, repeatRows=1, colWidths=[20*mm, 60*mm, 32*mm, 24*mm, 29*mm, 29*mm, 29*mm, 25*mm])
    cxp_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#17304F")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 6.5),
        ("ALIGN", (4,1), (6,-1), "RIGHT"),
        ("ALIGN", (7,1), (7,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#D9E1E8")),
        ("LEFTPADDING", (0,0), (-1,-1), 4), ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(cxp_table)

    def footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#667085"))
        canvas.drawString(12*mm, 7*mm, "CRV CONSTRUCTORA - Reporte generado por el sistema contable")
        canvas.drawRightString(landscape(A4)[0] - 12*mm, 7*mm, f"Página {doc_obj.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)

    nombre = f"CRV_reporte_contable_{date.today().isoformat()}.pdf"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=nombre,
        mimetype="application/pdf"
    )


@crv_bp.route("/reportes-contador/excel")
def reportes_contador_excel():
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    filtros = _reporte_filtros()
    datos = _datos_reportes_crv(empresa_id, filtros)
    resumen = datos["resumen"]

    wb = Workbook()
    ws = wb.active
    ws.title = "RESUMEN"

    navy = "17304F"
    gold = "D8B541"
    green = "0F8A47"
    red = "D92D20"
    light = "EEF3F8"
    white = "FFFFFF"
    gray = "667085"
    thin_gray = Side(style="thin", color="D9E1E8")

    def titulo_hoja(sheet, titulo, subtitulo=""):
        sheet.sheet_view.showGridLines = False
        sheet.merge_cells("A1:H1")
        c = sheet["A1"]
        c.value = titulo
        c.font = Font(size=18, bold=True, color=navy)
        c.alignment = Alignment(horizontal="left")
        if subtitulo:
            sheet.merge_cells("A2:H2")
            c2 = sheet["A2"]
            c2.value = subtitulo
            c2.font = Font(size=10, color=gray)
        sheet.row_dimensions[1].height = 28

    def encabezado(sheet, fila, headers):
        for col, valor in enumerate(headers, 1):
            cell = sheet.cell(fila, col, valor)
            cell.fill = PatternFill("solid", fgColor=navy)
            cell.font = Font(bold=True, color=white)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        sheet.row_dimensions[fila].height = 28

    def moneda(cell):
        cell.number_format = '$#,##0;[Red]($#,##0);-'
        cell.alignment = Alignment(horizontal="right")

    def auto_ancho(sheet, max_width=38):
        for col in range(1, sheet.max_column + 1):
            max_len = 0
            letter = get_column_letter(col)
            for row in range(1, min(sheet.max_row, 500) + 1):
                value = sheet.cell(row, col).value
                if value is not None:
                    max_len = max(max_len, len(str(value)))
            sheet.column_dimensions[letter].width = min(max(max_len + 2, 10), max_width)

    # RESUMEN
    titulo_hoja(ws, "CRV CONSTRUCTORA - REPORTE CONTABLE", f"Periodo: {_periodo_texto(filtros)}")
    ws["A4"] = "Indicador"
    ws["B4"] = "Valor"
    encabezado(ws, 4, ["Indicador", "Valor"])

    resumen_filas = [
        ("Ingresos", resumen["ingresos"]),
        ("Compras", resumen["compras"]),
        ("Gastos", resumen["gastos"]),
        ("Egresos totales", resumen["egresos"]),
        ("Resultado", resumen["resultado"]),
        ("CxP facturado", resumen["cxp_facturado"]),
        ("CxP pagado", resumen["cxp_pagado"]),
        ("CxP pendiente", resumen["cxp_pendiente"]),
        ("CxP vencido", resumen["cxp_vencido"]),
        ("Base gravable IVA", datos["iva_resumen"]["base_gravable"]),
        ("Base IVA generado", datos["iva_resumen"]["base_generado"]),
        ("Base IVA descontable", datos["iva_resumen"]["base_descontable"]),
        ("Base IVA mayor valor costo/gasto", datos["iva_resumen"]["base_mayor_valor"]),
        ("Base exenta", datos["iva_resumen"]["base_exenta"]),
        ("Base excluida", datos["iva_resumen"]["base_excluida"]),
        ("IVA generado", datos["iva_resumen"]["iva_generado"]),
        ("IVA descontable", datos["iva_resumen"]["iva_descontable"]),
        ("IVA mayor valor costo/gasto", datos["iva_resumen"]["iva_mayor_valor"]),
        ("Saldo IVA preliminar", datos["iva_resumen"]["saldo_iva_preliminar"]),
    ]
    for i, (label, valor) in enumerate(resumen_filas, 5):
        ws.cell(i, 1, label)
        ws.cell(i, 2, valor)
        moneda(ws.cell(i, 2))
        if label == "Resultado":
            ws.cell(i, 2).font = Font(bold=True, color=green if valor >= 0 else red)
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 20

    # MOVIMIENTOS
    mov_ws = wb.create_sheet("MOVIMIENTOS")
    titulo_hoja(mov_ws, "MOVIMIENTOS CONTABLES CRV", f"Periodo: {_periodo_texto(filtros)}")
    mov_headers = [
        "Fecha", "Tipo", "Categoría", "Subcategoría", "Tercero", "NIT/ID",
        "Documento", "Concepto", "Descripción", "Cuenta", "Cuenta destino",
        "Proyecto", "Centro costo", "Obra", "Base gravable", "Tipo IVA",
        "Tarifa IVA %", "Valor IVA", "Total documento", "Descuento",
        "Retención", "Otros descuentos", "Valor neto", "Forma pago",
        "Soporte", "Referencia", "Origen"
    ]
    encabezado(mov_ws, 4, mov_headers)
    for r, m in enumerate(datos["movimientos"], 5):
        vals = [
            m.fecha, m.tipo, m.categoria, m.subcategoria, m.nombre_tercero,
            m.tercero_identificacion, m.numero_documento, m.concepto, m.descripcion,
            m.cuenta, m.cuenta_destino, m.proyecto, m.centro_costo, m.obra,
            float(m.base_gravable or 0), m.tipo_iva or "NO_APLICA",
            float(m.tarifa_iva or 0), float(m.valor_iva or 0), float(m.valor or 0),
            float(m.descuento or 0), float(m.retencion or 0),
            float(m.otros_descuentos or 0), float(m.valor_neto or m.valor or 0),
            m.forma_pago, m.numero_soporte, m.referencia_pago, m.origen_registro
        ]
        for c, v in enumerate(vals, 1):
            mov_ws.cell(r, c, v)
        for c in (15, 18, 19, 20, 21, 22, 23):
            moneda(mov_ws.cell(r, c))
    mov_ws.freeze_panes = "A5"
    mov_ws.auto_filter.ref = f"A4:{get_column_letter(len(mov_headers))}{max(4, mov_ws.max_row)}"
    auto_ancho(mov_ws)

    # CUENTAS POR PAGAR
    cxp_ws = wb.create_sheet("CUENTAS_POR_PAGAR")
    titulo_hoja(cxp_ws, "CUENTAS POR PAGAR CRV", f"Periodo documento: {_periodo_texto(filtros)}")
    cxp_headers = [
        "Fecha", "Proveedor", "NIT/ID", "Tipo documento", "Documento", "Concepto",
        "Proyecto", "Centro costo", "Vencimiento", "Base gravable", "Tipo IVA",
        "Tarifa IVA %", "Valor IVA", "Total documento", "Descuento",
        "Retención", "Otros descuentos", "Neto", "Pagado", "Saldo", "Estado"
    ]
    encabezado(cxp_ws, 4, cxp_headers)
    for r, cta in enumerate(datos["cuentas"], 5):
        prov = cta.proveedor
        vals = [
            cta.fecha_documento,
            prov.razon_social if prov else "",
            prov.identificacion if prov else "",
            cta.tipo_documento,
            cta.numero_documento,
            cta.concepto,
            cta.proyecto,
            cta.centro_costo,
            cta.fecha_vencimiento,
            float(cta.base_gravable or 0),
            cta.tipo_iva or "NO_APLICA",
            float(cta.tarifa_iva or 0),
            float(cta.valor_iva or 0),
            float(cta.valor_bruto or 0),
            float(cta.descuento or 0),
            float(cta.retencion or 0),
            float(cta.otros_descuentos or 0),
            float(cta.valor_neto or 0),
            float(cta.total_pagado or 0),
            float(cta.saldo_pendiente or 0),
            cta.estado,
        ]
        for col, v in enumerate(vals, 1):
            cxp_ws.cell(r, col, v)
        for col in (10, 13, 14, 15, 16, 17, 18, 19, 20):
            moneda(cxp_ws.cell(r, col))
    cxp_ws.freeze_panes = "A5"
    cxp_ws.auto_filter.ref = f"A4:{get_column_letter(len(cxp_headers))}{max(4, cxp_ws.max_row)}"
    auto_ancho(cxp_ws)

    # IVA / IMPUESTOS
    iva_ws = wb.create_sheet("IVA")
    titulo_hoja(iva_ws, "RESUMEN DE IVA CRV", f"Periodo: {_periodo_texto(filtros)}")
    encabezado(iva_ws, 4, ["Concepto", "Valor"])
    iva_filas = [
        ("Base gravable IVA", datos["iva_resumen"]["base_gravable"]),
        ("Base IVA generado", datos["iva_resumen"]["base_generado"]),
        ("Base IVA descontable", datos["iva_resumen"]["base_descontable"]),
        ("Base IVA mayor valor costo/gasto", datos["iva_resumen"]["base_mayor_valor"]),
        ("Base exenta", datos["iva_resumen"]["base_exenta"]),
        ("Base excluida", datos["iva_resumen"]["base_excluida"]),
        ("IVA generado", datos["iva_resumen"]["iva_generado"]),
        ("IVA descontable", datos["iva_resumen"]["iva_descontable"]),
        ("IVA mayor valor costo/gasto", datos["iva_resumen"]["iva_mayor_valor"]),
        ("IVA total registrado", datos["iva_resumen"]["iva_total"]),
        ("Saldo IVA preliminar", datos["iva_resumen"]["saldo_iva_preliminar"]),
    ]
    for r, (concepto, valor) in enumerate(iva_filas, 5):
        iva_ws.cell(r, 1, concepto)
        iva_ws.cell(r, 2, valor)
        moneda(iva_ws.cell(r, 2))

    encabezado(iva_ws, 18, [
        "Fecha", "Tipo", "Tercero", "Documento", "Concepto",
        "Tipo IVA", "Tarifa %", "Base gravable", "Valor IVA", "Total documento"
    ])
    rr = 19
    for m in datos["movimientos"]:
        tipo_iva_mov = str(
            m.tipo_iva or "NO_APLICA"
        ).strip().upper()

        # La hoja tributaria incluye movimientos con tratamiento IVA,
        # incluso EXENTOS y EXCLUIDOS aunque su valor IVA sea cero.
        if tipo_iva_mov == "NO_APLICA":
            continue
        vals = [
            m.fecha, m.tipo, m.nombre_tercero, m.numero_documento or m.numero_soporte,
            m.concepto, m.tipo_iva, float(m.tarifa_iva or 0),
            float(m.base_gravable or 0), float(m.valor_iva or 0), float(m.valor or 0)
        ]
        for c, v in enumerate(vals, 1):
            iva_ws.cell(rr, c, v)
        for c in (8, 9, 10):
            moneda(iva_ws.cell(rr, c))
        rr += 1
    auto_ancho(iva_ws)

    # PROVEEDORES
    pr_ws = wb.create_sheet("PROVEEDORES")
    titulo_hoja(pr_ws, "RESUMEN POR PROVEEDOR", f"Periodo: {_periodo_texto(filtros)}")
    encabezado(pr_ws, 4, ["Proveedor", "NIT/ID", "Facturado", "Pagado", "Saldo", "Vencido"])
    for r, p in enumerate(datos["proveedores_resumen"], 5):
        vals = [p["nombre"], p["identificacion"], p["facturado"], p["pagado"], p["saldo"], p["vencido"]]
        for c, v in enumerate(vals, 1):
            pr_ws.cell(r, c, v)
        for c in range(3, 7):
            moneda(pr_ws.cell(r, c))
    auto_ancho(pr_ws)

    # PROYECTOS
    proy_ws = wb.create_sheet("PROYECTOS")
    titulo_hoja(proy_ws, "COSTOS POR PROYECTO Y CENTRO DE COSTO", f"Periodo: {_periodo_texto(filtros)}")
    encabezado(proy_ws, 4, ["Proyecto", "Centro de costo", "Movimientos", "Costo / egreso"])
    for r, p in enumerate(datos["proyectos_resumen"], 5):
        proy_ws.cell(r, 1, p["proyecto"])
        proy_ws.cell(r, 2, p["centro_costo"])
        proy_ws.cell(r, 3, p["movimientos"])
        proy_ws.cell(r, 4, p["total"])
        moneda(proy_ws.cell(r, 4))
    auto_ancho(proy_ws)

    # TERCEROS
    ter_ws = wb.create_sheet("TERCEROS")
    titulo_hoja(ter_ws, "DIRECTORIO DE TERCEROS CRV", "Información registrada en el sistema")
    ter_headers = [
        "Tipo", "Tipo documento", "Identificación", "Razón social", "Nombre comercial",
        "Dirección", "Ciudad", "Departamento", "Teléfono", "Celular", "Email",
        "Contacto", "Banco", "Tipo cuenta", "Número cuenta", "Titular cuenta", "Activo"
    ]
    encabezado(ter_ws, 4, ter_headers)
    for r, t in enumerate(datos["terceros"], 5):
        vals = [
            t.tipo_tercero, t.tipo_documento, t.identificacion, t.razon_social,
            t.nombre_comercial, t.direccion, t.ciudad, t.departamento, t.telefono,
            t.celular, t.email, t.contacto, t.banco, t.tipo_cuenta, t.numero_cuenta,
            t.titular_cuenta, "SI" if t.activo else "NO"
        ]
        for c, v in enumerate(vals, 1):
            ter_ws.cell(r, c, v)
    ter_ws.freeze_panes = "A5"
    ter_ws.auto_filter.ref = f"A4:{get_column_letter(len(ter_headers))}{max(4, ter_ws.max_row)}"
    auto_ancho(ter_ws)

    for sheet in wb.worksheets:
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
        sheet.sheet_view.showGridLines = False

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    nombre = f"CRV_reporte_contable_{date.today().isoformat()}.xlsx"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=nombre,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@crv_bp.route("/reportes-contador")
def reportes_contador():
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "CRV CONSTRUCTORA")
    filtros = _reporte_filtros()
    datos = _datos_reportes_crv(empresa_id, filtros)

    tipos = [
        fila[0]
        for fila in db.session.query(CRVMovimiento.tipo)
        .filter(CRVMovimiento.empresa_id == empresa_id)
        .distinct()
        .order_by(CRVMovimiento.tipo.asc())
        .all()
        if fila[0]
    ]

    proyectos = [
        fila[0]
        for fila in db.session.query(CRVMovimiento.proyecto)
        .filter(
            CRVMovimiento.empresa_id == empresa_id,
            CRVMovimiento.proyecto.isnot(None),
            CRVMovimiento.proyecto != ""
        )
        .distinct()
        .order_by(CRVMovimiento.proyecto.asc())
        .all()
        if fila[0]
    ]

    centros = [
        fila[0]
        for fila in db.session.query(CRVMovimiento.centro_costo)
        .filter(
            CRVMovimiento.empresa_id == empresa_id,
            CRVMovimiento.centro_costo.isnot(None),
            CRVMovimiento.centro_costo != ""
        )
        .distinct()
        .order_by(CRVMovimiento.centro_costo.asc())
        .all()
        if fila[0]
    ]

    return render_template(
        "contabilidad/crv_reportes.html",
        empresa_nombre=empresa_nombre,
        filtros=filtros,
        periodo=_periodo_texto(filtros),
        tipos=tipos,
        proyectos=proyectos,
        centros=centros,
        movimientos=datos["movimientos"],
        cuentas=datos["cuentas"],
        terceros=datos["terceros"],
        resumen=datos["resumen"],
        iva_resumen=datos["iva_resumen"],
        proveedores_resumen=datos["proveedores_resumen"],
        proyectos_resumen=datos["proyectos_resumen"]
    )


@crv_bp.route("/exportaciones")
def exportaciones_crv():

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    return render_template(
        "contabilidad/crv_exportaciones.html",
        empresa_nombre=session.get(
            "empresa_nombre",
            "CRV CONSTRUCTORA"
        )
    )


__all__ = ['exportaciones_crv', 'reportes_contador', 'reportes_contador_excel', 'reportes_contador_pdf']
