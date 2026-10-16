"""CRV report routes: cuentas."""

from .crv_core import (
    CRVCuentaCobrar,
    CRVCuentaPagar,
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


@crv_bp.route("/cuentas-por-pagar/pdf")
def cuentas_pagar_pdf():

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    cuentas = (
        CRVCuentaPagar.query
        .filter_by(
            empresa_id=empresa_id
        )
        .order_by(
            CRVCuentaPagar.fecha_documento.asc(),
            CRVCuentaPagar.id.asc()
        )
        .all()
    )

    filas = []

    for cta in cuentas:
        prov = cta.proveedor

        filas.append([
            (
                cta.fecha_documento.strftime(
                    "%d/%m/%Y"
                )
                if cta.fecha_documento
                else ""
            ),
            (
                prov.razon_social
                if prov
                else ""
            ),
            cta.numero_documento or "",
            cta.concepto or "",
            (
                cta.fecha_vencimiento.strftime(
                    "%d/%m/%Y"
                )
                if cta.fecha_vencimiento
                else ""
            ),
            _money_export(
                cta.base_gravable
            ),
            _money_export(
                cta.valor_iva
            ),
            _money_export(
                cta.valor_bruto
            ),
            _money_export(
                cta.valor_neto
            ),
            _money_export(
                cta.total_pagado
            ),
            _money_export(
                cta.saldo_pendiente
            ),
            cta.estado or ""
        ])

    story = []

    _pdf_encabezado_historia(
        story,
        "CRV CONSTRUCTORA - CUENTAS POR PAGAR",
        (
            "Cartera general de proveedores · "
            f"Generado {date.today().strftime('%d/%m/%Y')}"
        )
    )

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
                "Estado"
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
                20 * mm
            ]
        )
    )

    return _enviar_pdf(
        story,
        (
            f"CRV_cuentas_por_pagar_"
            f"{date.today().isoformat()}.pdf"
        )
    )


@crv_bp.route("/cuentas-por-pagar/excel")
def cuentas_pagar_excel():

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    cuentas = (
        CRVCuentaPagar.query
        .filter_by(
            empresa_id=empresa_id
        )
        .order_by(
            CRVCuentaPagar.fecha_documento.asc(),
            CRVCuentaPagar.id.asc()
        )
        .all()
    )

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
        "Estado"
    ]

    _excel_titulo(
        ws,
        "CRV CONSTRUCTORA - CUENTAS POR PAGAR",
        (
            "Cartera de proveedores y obligaciones "
            f"· Generado {date.today().strftime('%d/%m/%Y')}"
        ),
        len(headers)
    )

    _excel_encabezado(
        ws,
        4,
        headers
    )

    for fila, cta in enumerate(
        cuentas,
        5
    ):
        prov = cta.proveedor

        valores = [
            cta.fecha_documento,
            (
                prov.razon_social
                if prov
                else ""
            ),
            (
                prov.identificacion
                if prov
                else ""
            ),
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
            cta.estado
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

        for col in (10, 13, 14, 15, 16, 17, 18, 19, 20):
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
            f"CRV_cuentas_por_pagar_"
            f"{date.today().isoformat()}.xlsx"
        )
    )


__all__ = ['cuentas_cobrar_excel', 'cuentas_cobrar_pdf', 'cuentas_pagar_excel', 'cuentas_pagar_pdf']
