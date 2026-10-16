"""CRV reportes exports service helpers."""

from ..crv_context import (
    A4,
    Alignment,
    BytesIO,
    Font,
    Image,
    Paragraph,
    ParagraphStyle,
    Path,
    PatternFill,
    SimpleDocTemplate,
    Spacer,
    TA_CENTER,
    TA_LEFT,
    Table,
    TableStyle,
    colors,
    current_app,
    escape,
    getSampleStyleSheet,
    get_column_letter,
    landscape,
    mm,
    send_file,
)

def _excel_estilos_base():
    return {
        "navy": "17304F",
        "gold": "D8B541",
        "green": "0F8A47",
        "red": "D92D20",
        "light": "EEF3F8",
        "white": "FFFFFF",
        "gray": "667085",
    }

def _excel_titulo(sheet, titulo, subtitulo="", columnas=10):
    estilos = _excel_estilos_base()
    navy = estilos["navy"]
    gray = estilos["gray"]

    sheet.sheet_view.showGridLines = False

    sheet.merge_cells(
        start_row=1,
        start_column=1,
        end_row=1,
        end_column=max(2, columnas)
    )

    c = sheet.cell(1, 1)
    c.value = titulo
    c.font = Font(
        size=18,
        bold=True,
        color=navy
    )
    c.alignment = Alignment(
        horizontal="left",
        vertical="center"
    )

    if subtitulo:
        sheet.merge_cells(
            start_row=2,
            start_column=1,
            end_row=2,
            end_column=max(2, columnas)
        )
        c2 = sheet.cell(2, 1)
        c2.value = subtitulo
        c2.font = Font(
            size=10,
            color=gray
        )

    sheet.row_dimensions[1].height = 28

def _excel_encabezado(sheet, fila, headers):
    estilos = _excel_estilos_base()

    for col, valor in enumerate(headers, 1):
        cell = sheet.cell(fila, col, valor)
        cell.fill = PatternFill(
            "solid",
            fgColor=estilos["navy"]
        )
        cell.font = Font(
            bold=True,
            color=estilos["white"]
        )
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True
        )

    sheet.row_dimensions[fila].height = 28

def _excel_moneda(cell):
    cell.number_format = '$#,##0;[Red]($#,##0);-'
    cell.alignment = Alignment(
        horizontal="right"
    )

def _excel_auto_ancho(sheet, max_width=40):
    for col in range(
        1,
        sheet.max_column + 1
    ):
        letter = get_column_letter(col)
        max_len = 0

        for row in range(
            1,
            min(sheet.max_row, 1000) + 1
        ):
            value = sheet.cell(
                row,
                col
            ).value

            if value is not None:
                max_len = max(
                    max_len,
                    len(str(value))
                )

        sheet.column_dimensions[
            letter
        ].width = min(
            max(max_len + 2, 10),
            max_width
        )

def _enviar_excel(wb, nombre_archivo):
    for sheet in wb.worksheets:
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
        sheet.sheet_view.showGridLines = False

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=nombre_archivo,
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )

def _pdf_estilos_crv():
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CRVExportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=21,
        textColor=colors.HexColor("#17304F"),
        alignment=TA_CENTER
    )

    subtitle_style = ParagraphStyle(
        "CRVExportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#667085"),
        alignment=TA_CENTER
    )

    section_style = ParagraphStyle(
        "CRVExportSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        textColor=colors.HexColor("#17304F"),
        spaceBefore=5,
        spaceAfter=7
    )

    small_style = ParagraphStyle(
        "CRVExportSmall",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.7,
        leading=8,
        textColor=colors.HexColor("#25364A"),
        alignment=TA_LEFT
    )

    return (
        title_style,
        subtitle_style,
        section_style,
        small_style
    )

def _pdf_encabezado_historia(story, titulo, subtitulo=""):
    (
        title_style,
        subtitle_style,
        _,
        _
    ) = _pdf_estilos_crv()

    logo_path = (
        Path(current_app.root_path)
        / "static"
        / "logo_crv.png"
    )

    if logo_path.exists():
        story.append(
            Image(
                str(logo_path),
                width=24 * mm,
                height=18 * mm
            )
        )

    story.append(
        Paragraph(
            titulo,
            title_style
        )
    )

    if subtitulo:
        story.append(
            Paragraph(
                subtitulo,
                subtitle_style
            )
        )

    story.append(
        Spacer(
            1,
            5 * mm
        )
    )

def _pdf_tabla(headers, filas, widths=None):
    _, _, _, small = _pdf_estilos_crv()

    data = [
        [
            Paragraph(
                str(h),
                small
            )
            for h in headers
        ]
    ]

    for fila in filas:
        data.append([
            Paragraph(
                str(v if v not in (None, "") else "-"),
                small
            )
            for v in fila
        ])

    tabla = Table(
        data,
        colWidths=widths,
        repeatRows=1,
        hAlign="LEFT"
    )

    tabla.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#17304F")
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold"
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP"
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.35,
                colors.HexColor("#D9E1E8")
            ),
            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [
                    colors.white,
                    colors.HexColor("#F8FAFC")
                ]
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                4
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                4
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                4
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                4
            ),
        ])
    )

    return tabla

def _enviar_pdf(story, nombre_archivo, horizontal=True):
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=(
            landscape(A4)
            if horizontal
            else A4
        ),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm
    )

    doc.build(story)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=nombre_archivo,
        mimetype="application/pdf"
    )

def _money_export(v):
    return f"${float(v or 0):,.0f}"

def _texto_pdf_seguro(valor):
    return escape(
        str(valor or "")
    )

__all__ = ['_enviar_excel', '_enviar_pdf', '_excel_auto_ancho', '_excel_encabezado', '_excel_estilos_base', '_excel_moneda', '_excel_titulo', '_money_export', '_pdf_encabezado_historia', '_pdf_estilos_crv', '_pdf_tabla', '_texto_pdf_seguro']
