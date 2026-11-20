"""CRV report routes: cuentas."""

from httpcore import request
from flask import request

from .crv_core import (
    CRVCuentaCobrar,
    CRVCuentaPagar,
    CRVTercero,
    db,
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
    crv_bp,
    date,
    get_column_letter,
    mm,
    proteger_crv,
    session,
)

@crv_bp.route("/cuentas-por-cobrar/excel")
def cuentas_cobrar_excel():
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    cuentas = CRVCuentaCobrar.query.filter_by(empresa_id=empresa_id).order_by(
        CRVCuentaCobrar.fecha_documento.asc(), CRVCuentaCobrar.id.asc()
    ).all()

    for c in cuentas:
        c.recalcular_saldos()

    wb = Workbook()
    ws = wb.active
    ws.title = "CUENTAS_POR_COBRAR"

    headers = [
        "Fecha", "Cliente", "NIT/ID", "Tipo documento", "Documento",
        "Concepto", "Proyecto", "Centro costo", "Vencimiento",
        "Base gravable", "Tipo IVA", "Tarifa IVA %", "Valor IVA", "Total documento",
        "Descuento", "Retención", "Otros descuentos",
        "Neto", "Cobrado", "Saldo", "Estado"
    ]

    _excel_titulo(ws, "CRV CONSTRUCTORA - CUENTAS POR COBRAR",
                  f"Cartera de clientes · Generado {date.today().strftime('%d/%m/%Y')}", len(headers))
    _excel_encabezado(ws, 4, headers)

    for fila, c in enumerate(cuentas, 5):
        cli = c.cliente
        valores = [
            c.fecha_documento,
            cli.razon_social if cli else "",
            cli.identificacion if cli else "",
            c.tipo_documento,
            c.numero_documento,
            c.concepto,
            c.proyecto,
            c.centro_costo,
            c.fecha_vencimiento,
            float(c.base_gravable or 0),
            c.tipo_iva or "NO_APLICA",
            float(c.tarifa_iva or 0),
            float(c.valor_iva or 0),
            float(c.valor_bruto or 0),
            float(c.descuento or 0),
            float(c.retencion or 0),
            float(c.otros_descuentos or 0),
            float(c.valor_neto or 0),
            float(c.total_cobrado or 0),
            float(c.saldo_pendiente or 0),
            c.estado,
        ]
        for col, valor in enumerate(valores, 1):
            ws.cell(fila, col, valor)
        for col in (10, 13, 14, 15, 16, 17, 18, 19, 20):
            _excel_moneda(ws.cell(fila, col))

    ws.freeze_panes = "A5"
    ws.auto_filter.ref = f"A4:{get_column_letter(len(headers))}{max(4, ws.max_row)}"
    _excel_auto_ancho(ws)

    return _enviar_excel(wb, f"CRV_cuentas_por_cobrar_{date.today().isoformat()}.xlsx")


@crv_bp.route("/cuentas-por-cobrar/pdf")
def cuentas_cobrar_pdf():
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    cuentas = CRVCuentaCobrar.query.filter_by(empresa_id=empresa_id).order_by(
        CRVCuentaCobrar.fecha_documento.asc(), CRVCuentaCobrar.id.asc()
    ).all()

    filas = []
    for c in cuentas:
        c.recalcular_saldos()
        cli = c.cliente
        filas.append([
            c.fecha_documento.strftime("%d/%m/%Y") if c.fecha_documento else "",
            cli.razon_social if cli else "",
            c.numero_documento or "",
            c.concepto or "",
            c.fecha_vencimiento.strftime("%d/%m/%Y") if c.fecha_vencimiento else "",
            _money_export(c.base_gravable),
            _money_export(c.valor_iva),
            _money_export(c.valor_bruto),
            _money_export(c.valor_neto),
            _money_export(c.total_cobrado),
            _money_export(c.saldo_pendiente),
            c.estado or ""
        ])

    story = []
    _pdf_encabezado_historia(
        story,
        "CRV CONSTRUCTORA - CUENTAS POR COBRAR",
        f"Cartera general de clientes · Generado {date.today().strftime('%d/%m/%Y')}"
    )
    story.append(_pdf_tabla(
        ["Fecha", "Cliente", "Documento", "Concepto", "Vence", "Base", "IVA", "Total", "Neto", "Cobrado", "Saldo", "Estado"],
        filas,
        [18*mm, 38*mm, 22*mm, 38*mm, 18*mm, 21*mm, 19*mm, 21*mm, 21*mm, 21*mm, 21*mm, 20*mm]
    ))

    return _enviar_pdf(story, f"CRV_cuentas_por_cobrar_{date.today().isoformat()}.pdf")


from reportlab.lib import colors
from reportlab.platypus import Spacer, Table, TableStyle
def _consultar_cuentas_pagar_export(empresa_id):
    """Filtra las cuentas por pagar y calcula los totales para PDF y Excel."""
    proveedor_id = request.args.get("proveedor_id", "").strip()
    estado = request.args.get("estado", "").strip().upper()
    mes = request.args.get("mes", "").strip()
    buscar = request.args.get("buscar", "").strip()

    query = CRVCuentaPagar.query.filter_by(empresa_id=empresa_id)

    if proveedor_id.isdigit():
        query = query.filter_by(proveedor_id=int(proveedor_id))

    if estado:
        query = query.filter(CRVCuentaPagar.estado == estado)

    if mes:
        try:
            anio_texto, mes_texto = mes.split("-")
            query = query.filter(
                db.extract("year", CRVCuentaPagar.fecha_documento) == int(anio_texto),
                db.extract("month", CRVCuentaPagar.fecha_documento) == int(mes_texto),
            )
        except (ValueError, TypeError):
            pass

    if buscar:
        patron = f"%{buscar}%"
        query = query.join(
            CRVTercero,
            CRVCuentaPagar.proveedor_id == CRVTercero.id,
        ).filter(
            db.or_(
                CRVCuentaPagar.numero_documento.ilike(patron),
                CRVCuentaPagar.concepto.ilike(patron),
                CRVTercero.razon_social.ilike(patron),
                CRVTercero.identificacion.ilike(patron),
            )
        )

    cuentas = query.order_by(
        CRVCuentaPagar.fecha_documento.asc(),
        CRVCuentaPagar.id.asc(),
    ).all()

    for cta in cuentas:
        cta.recalcular_estado()

    totales = {
        "facturado": sum(float(c.valor_neto or 0) for c in cuentas),
        "pagado": sum(float(c.total_pagado or 0) for c in cuentas),
        "pendiente": sum(float(c.saldo_pendiente or 0) for c in cuentas),
        "vencido": sum(
            float(c.saldo_pendiente or 0)
            for c in cuentas
            if c.estado == "VENCIDA"
        ),
    }

    filtros = {
        "mes": mes,
        "estado": estado,
        "buscar": buscar,
    }

    return cuentas, totales, filtros


@crv_bp.route("/cuentas-por-pagar/pdf")
def cuentas_pagar_pdf():
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    cuentas, totales, filtros = _consultar_cuentas_pagar_export(empresa_id)

    filas = []

    for cta in cuentas:
        prov = cta.proveedor

        filas.append([
            cta.fecha_documento.strftime("%d/%m/%Y") if cta.fecha_documento else "",
            prov.razon_social if prov else "",
            cta.numero_documento or "",
            cta.concepto or "",
            cta.fecha_vencimiento.strftime("%d/%m/%Y") if cta.fecha_vencimiento else "-",
            _money_export(cta.base_gravable),
            _money_export(cta.valor_iva),
            _money_export(cta.valor_bruto),
            _money_export(cta.valor_neto),
            _money_export(cta.total_pagado),
            _money_export(cta.saldo_pendiente),
            cta.estado or "",
        ])

    filtros_texto = []
    if filtros["mes"]:
        filtros_texto.append(f"Mes: {filtros['mes']}")
    if filtros["estado"]:
        filtros_texto.append(f"Estado: {filtros['estado']}")
    if filtros["buscar"]:
        filtros_texto.append(f"Búsqueda: {filtros['buscar']}")

    subtitulo = (
        " · ".join(filtros_texto)
        if filtros_texto
        else "Cartera general de proveedores"
    )
    subtitulo += f" · Generado {date.today().strftime('%d/%m/%Y')}"

    story = []

    _pdf_encabezado_historia(
        story,
        "CRV CONSTRUCTORA - CUENTAS POR PAGAR",
        subtitulo,
    )

    # Cuadro de resumen superior (Total facturado, pagado, saldo pendiente y mora)
    datos_resumen = [[
        f"TOTAL FACTURADO\n{_money_export(totales['facturado'])}",
        f"TOTAL PAGADO\n{_money_export(totales['pagado'])}",
        f"SALDO PENDIENTE\n{_money_export(totales['pendiente'])}",
        f"CARTERA VENCIDA (MORA)\n{_money_export(totales['vencido'])}",
    ]]

    tabla_resumen = Table(datos_resumen, colWidths=[64 * mm, 64 * mm, 64 * mm, 66 * mm])
    tabla_resumen.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.75, colors.HexColor("#cbd5e1")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#17283f")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("LEADING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("LINEABOVE", (0, 0), (0, 0), 2.5, colors.HexColor("#d8b541")),
        ("LINEABOVE", (1, 0), (1, 0), 2.5, colors.HexColor("#16a05b")),
        ("LINEABOVE", (2, 0), (2, 0), 2.5, colors.HexColor("#17304f")),
        ("LINEABOVE", (3, 0), (3, 0), 2.5, colors.HexColor("#ef2b2d")),
    ]))

    story.append(tabla_resumen)
    story.append(Spacer(1, 5 * mm))

    story.append(
        _pdf_tabla(
            [
                "Fecha",
                "Proveedor",
                "Documento",
                "Concepto",
                "Vence",
                "Base",
                "IVA",
                "Total",
                "Neto",
                "Pagado",
                "Saldo",
                "Estado",
            ],
            filas,
            [
                18 * mm,
                38 * mm,
                22 * mm,
                38 * mm,
                18 * mm,
                21 * mm,
                19 * mm,
                21 * mm,
                21 * mm,
                21 * mm,
                21 * mm,
                20 * mm,
            ],
        )
    )

    return _enviar_pdf(
        story,
        f"CRV_cuentas_por_pagar_{date.today().isoformat()}.pdf",
    )


@crv_bp.route("/cuentas-por-pagar/excel")
def cuentas_pagar_excel():
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    cuentas, totales, filtros = _consultar_cuentas_pagar_export(empresa_id)

    wb = Workbook()
    ws = wb.active
    ws.title = "CUENTAS_POR_PAGAR"

    headers = [
        "Fecha",
        "Proveedor",
        "NIT/ID",
        "Tipo documento",
        "Documento",
        "Concepto",
        "Proyecto",
        "Centro costo",
        "Vencimiento",
        "Base gravable",
        "Tipo IVA",
        "Tarifa IVA %",
        "Valor IVA",
        "Total documento",
        "Descuento",
        "Retención",
        "Otros descuentos",
        "Neto",
        "Pagado",
        "Saldo",
        "Estado",
    ]

    filtros_texto = []
    if filtros["mes"]:
        filtros_texto.append(f"Mes: {filtros['mes']}")
    if filtros["estado"]:
        filtros_texto.append(f"Estado: {filtros['estado']}")
    if filtros["buscar"]:
        filtros_texto.append(f"Búsqueda: {filtros['buscar']}")

    subtitulo = (
        " · ".join(filtros_texto)
        if filtros_texto
        else "Cartera de proveedores y obligaciones"
    )
    subtitulo += f" · Generado {date.today().strftime('%d/%m/%Y')}"

    _excel_titulo(
        ws,
        "CRV CONSTRUCTORA - CUENTAS POR PAGAR",
        subtitulo,
        len(headers),
    )

    # Fila 4: Resumen financiero (Total facturado, pagado, pendiente y mora)
    ws.cell(4, 1, "TOTAL FACTURADO:")
    ws.cell(4, 2, totales["facturado"])
    _excel_moneda(ws.cell(4, 2))

    ws.cell(4, 4, "TOTAL PAGADO:")
    ws.cell(4, 5, totales["pagado"])
    _excel_moneda(ws.cell(4, 5))

    ws.cell(4, 7, "SALDO PENDIENTE:")
    ws.cell(4, 8, totales["pendiente"])
    _excel_moneda(ws.cell(4, 8))

    ws.cell(4, 10, "CARTERA VENCIDA (MORA):")
    ws.cell(4, 11, totales["vencido"])
    _excel_moneda(ws.cell(4, 11))

    # Encabezados de la tabla en fila 6
    _excel_encabezado(ws, 6, headers)

    for fila, cta in enumerate(cuentas, 7):
        prov = cta.proveedor

        valores = [
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

        for col, valor in enumerate(valores, 1):
            ws.cell(fila, col, valor)

        for col in (10, 13, 14, 15, 16, 17, 18, 19, 20):
            _excel_moneda(ws.cell(fila, col))

    ws.freeze_panes = "A7"
    ws.auto_filter.ref = (
        f"A6:"
        f"{get_column_letter(len(headers))}"
        f"{max(6, ws.max_row)}"
    )

    _excel_auto_ancho(ws)

    return _enviar_excel(
        wb,
        f"CRV_cuentas_por_pagar_{date.today().isoformat()}.xlsx",
    )


__all__ = ['cuentas_cobrar_excel', 'cuentas_cobrar_pdf', 'cuentas_pagar_excel', 'cuentas_pagar_pdf']
