"""CRV report routes: bancos."""

from .crv_core import (
    CRVMovimiento,
    Paragraph,
    Spacer,
    Workbook,
    _conciliacion_periodo,
    _cuentas_financieras_crv,
    _enviar_excel,
    _enviar_pdf,
    _excel_auto_ancho,
    _excel_encabezado,
    _excel_moneda,
    _excel_titulo,
    _impacto_bancario_movimiento,
    _money_export,
    _movimiento_es_bancario,
    _movimientos_cuenta_periodo,
    _pdf_encabezado_historia,
    _pdf_estilos_crv,
    _pdf_tabla,
    _rango_mes,
    _saldo_cuenta_hasta,
    crv_bp,
    date,
    get_column_letter,
    mm,
    proteger_crv,
    request,
    session,
)

@crv_bp.route("/bancos-caja/pdf")
def bancos_caja_pdf():

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    cuentas = _cuentas_financieras_crv(
        empresa_id
    )

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

    movimientos = [
        m
        for m in movimientos
        if _movimiento_es_bancario(m)
    ]

    story = []

    _pdf_encabezado_historia(
        story,
        "CRV CONSTRUCTORA - BANCOS Y CAJA",
        (
            "Reporte para conciliación bancaria · "
            f"Generado {date.today().strftime('%d/%m/%Y')}"
        )
    )

    filas_saldos = []

    for c in cuentas:
        filas_saldos.append([
            c["nombre"],
            _money_export(c["saldo"]),
            _money_export(c["ingresos"]),
            _money_export(c["egresos"]),
            c["movimientos"],
            c["sin_conciliar"]
        ])

    story.append(
        Paragraph(
            "Resumen por cuenta",
            _pdf_estilos_crv()[2]
        )
    )

    story.append(
        _pdf_tabla(
            [
                "Cuenta CRV",
                "Saldo",
                "Entradas",
                "Egresos",
                "Movimientos",
                "Sin conciliar"
            ],
            filas_saldos,
            [
                65 * mm,
                34 * mm,
                34 * mm,
                34 * mm,
                27 * mm,
                27 * mm
            ]
        )
    )

    story.append(
        Spacer(
            1,
            5 * mm
        )
    )

    story.append(
        Paragraph(
            "Movimientos bancarios",
            _pdf_estilos_crv()[2]
        )
    )

    filas_mov = []

    for m in movimientos:
        filas_mov.append([
            (
                m.fecha.strftime("%d/%m/%Y")
                if m.fecha
                else ""
            ),
            m.tipo or "",
            m.cuenta or "",
            (
                m.cuenta_destino
                if str(
                    m.tipo or ""
                ).strip().upper() == "TRANSFERENCIA"
                else (
                    m.nombre_tercero
                    or m.beneficiario
                    or ""
                )
            ),
            m.concepto or "",
            _money_export(
                m.valor_neto
                or m.valor
                or 0
            ),
            (
                "CONCILIADO"
                if m.revisado
                else "PENDIENTE"
            )
        ])

    story.append(
        _pdf_tabla(
            [
                "Fecha",
                "Tipo",
                "Cuenta origen",
                "Destino / beneficiario",
                "Concepto",
                "Valor",
                "Conciliación"
            ],
            filas_mov,
            [
                20 * mm,
                30 * mm,
                38 * mm,
                48 * mm,
                65 * mm,
                28 * mm,
                28 * mm
            ]
        )
    )

    return _enviar_pdf(
        story,
        (
            f"CRV_bancos_y_caja_"
            f"{date.today().isoformat()}.pdf"
        )
    )


@crv_bp.route("/bancos-caja/excel")
def bancos_caja_excel():

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    cuentas = _cuentas_financieras_crv(
        empresa_id
    )

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

    movimientos = [
        m
        for m in movimientos
        if _movimiento_es_bancario(m)
    ]

    wb = Workbook()

    ws = wb.active
    ws.title = "SALDOS"

    _excel_titulo(
        ws,
        "CRV CONSTRUCTORA - BANCOS Y CAJA",
        (
            "Saldos calculados de cuentas propias "
            f"· Generado {date.today().strftime('%d/%m/%Y')}"
        ),
        9
    )

    headers_saldos = [
        "Cuenta CRV",
        "Saldo",
        "Entradas",
        "Egresos",
        "Transferencias entrada",
        "Transferencias salida",
        "Movimientos",
        "Sin conciliar",
        "Estado"
    ]

    _excel_encabezado(
        ws,
        4,
        headers_saldos
    )

    for fila, c in enumerate(
        cuentas,
        5
    ):
        valores = [
            c["nombre"],
            c["saldo"],
            c["ingresos"],
            c["egresos"],
            c["transferencias_entrada"],
            c["transferencias_salida"],
            c["movimientos"],
            c["sin_conciliar"],
            "ACTIVA"
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
            2,
            7
        ):
            _excel_moneda(
                ws.cell(
                    fila,
                    col
                )
            )

    _excel_auto_ancho(ws)

    mov_ws = wb.create_sheet(
        "MOVIMIENTOS_BANCARIOS"
    )

    mov_headers = [
        "Fecha",
        "Tipo",
        "Cuenta origen CRV",
        "Cuenta destino / beneficiario",
        "Concepto",
        "Tercero / beneficiario",
        "Documento",
        "Soporte",
        "Referencia",
        "Valor",
        "Conciliado"
    ]

    _excel_titulo(
        mov_ws,
        "MOVIMIENTOS BANCARIOS Y DE CAJA",
        "Únicamente movimientos asociados a cuentas propias de CRV",
        len(mov_headers)
    )

    _excel_encabezado(
        mov_ws,
        4,
        mov_headers
    )

    for fila, m in enumerate(
        movimientos,
        5
    ):
        valores = [
            m.fecha,
            m.tipo,
            m.cuenta,
            m.cuenta_destino,
            m.concepto,
            (
                m.nombre_tercero
                or m.beneficiario
                or ""
            ),
            m.numero_documento,
            m.numero_soporte,
            m.referencia_pago,
            float(
                m.valor_neto
                or m.valor
                or 0
            ),
            (
                "SI"
                if m.revisado
                else "NO"
            )
        ]

        for col, valor in enumerate(
            valores,
            1
        ):
            mov_ws.cell(
                fila,
                col,
                valor
            )

        _excel_moneda(
            mov_ws.cell(
                fila,
                10
            )
        )

    mov_ws.freeze_panes = "A5"
    mov_ws.auto_filter.ref = (
        f"A4:"
        f"{get_column_letter(len(mov_headers))}"
        f"{max(4, mov_ws.max_row)}"
    )

    _excel_auto_ancho(mov_ws)

    return _enviar_excel(
        wb,
        (
            f"CRV_bancos_y_caja_"
            f"{date.today().isoformat()}.xlsx"
        )
    )


@crv_bp.route(
    "/conciliacion-bancaria/pdf"
)
def conciliacion_bancaria_pdf():

    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get(
        "empresa_id"
    )

    periodo = request.args.get(
        "periodo",
        ""
    ).strip()

    cuenta = request.args.get(
        "cuenta",
        ""
    ).strip()

    try:
        anio, mes = [
            int(x)
            for x in periodo.split("-")
        ]
    except (ValueError, TypeError):
        hoy = date.today()
        anio = hoy.year
        mes = hoy.month
        periodo = (
            f"{anio}-"
            f"{mes:02d}"
        )

    _, fecha_fin = _rango_mes(
        anio,
        mes
    )

    movimientos = _movimientos_cuenta_periodo(
        empresa_id,
        cuenta,
        anio,
        mes
    )

    saldo_sistema = _saldo_cuenta_hasta(
        empresa_id,
        cuenta,
        fecha_fin
    )

    conciliacion = _conciliacion_periodo(
        empresa_id,
        cuenta,
        anio,
        mes
    )

    saldo_extracto = (
        float(
            conciliacion.saldo_extracto
            or 0
        )
        if conciliacion
        else 0
    )

    story = []

    _pdf_encabezado_historia(
        story,
        "CRV CONSTRUCTORA - CONCILIACIÓN BANCARIA",
        (
            f"Cuenta: {cuenta} · Periodo: {periodo}"
        )
    )

    story.append(
        _pdf_tabla(
            [
                "Saldo sistema",
                "Saldo extracto",
                "Diferencia",
                "Estado"
            ],
            [[
                _money_export(
                    saldo_sistema
                ),
                _money_export(
                    saldo_extracto
                ),
                _money_export(
                    saldo_extracto
                    - saldo_sistema
                ),
                (
                    conciliacion.estado
                    if conciliacion
                    else "PENDIENTE"
                )
            ]],
            [
                45 * mm,
                45 * mm,
                45 * mm,
                35 * mm
            ]
        )
    )

    story.append(
        Spacer(
            1,
            5 * mm
        )
    )

    filas = []

    for m in movimientos:
        impacto = _impacto_bancario_movimiento(
            m,
            cuenta
        )

        filas.append([
            (
                m.fecha.strftime(
                    "%d/%m/%Y"
                )
                if m.fecha
                else ""
            ),
            m.tipo or "",
            m.nombre_tercero or "",
            m.concepto or "",
            _money_export(
                max(
                    0,
                    impacto
                )
            ),
            _money_export(
                abs(
                    min(
                        0,
                        impacto
                    )
                )
            ),
            (
                "SI"
                if m.revisado
                else "NO"
            )
        ])

    story.append(
        _pdf_tabla(
            [
                "Fecha",
                "Tipo",
                "Tercero",
                "Concepto",
                "Entrada",
                "Salida",
                "Conciliado"
            ],
            filas,
            [
                20 * mm,
                30 * mm,
                45 * mm,
                65 * mm,
                28 * mm,
                28 * mm,
                24 * mm
            ]
        )
    )

    return _enviar_pdf(
        story,
        (
            "CRV_conciliacion_"
            f"{cuenta.replace(' ', '_')}_"
            f"{periodo}.pdf"
        )
    )


@crv_bp.route(
    "/conciliacion-bancaria/excel"
)
def conciliacion_bancaria_excel():

    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get(
        "empresa_id"
    )

    periodo = request.args.get(
        "periodo",
        ""
    ).strip()

    cuenta = request.args.get(
        "cuenta",
        ""
    ).strip()

    try:
        anio, mes = [
            int(x)
            for x in periodo.split("-")
        ]
    except (ValueError, TypeError):
        hoy = date.today()
        anio = hoy.year
        mes = hoy.month
        periodo = (
            f"{anio}-"
            f"{mes:02d}"
        )

    _, fecha_fin = _rango_mes(
        anio,
        mes
    )

    movimientos = _movimientos_cuenta_periodo(
        empresa_id,
        cuenta,
        anio,
        mes
    )

    saldo_sistema = _saldo_cuenta_hasta(
        empresa_id,
        cuenta,
        fecha_fin
    )

    conciliacion = _conciliacion_periodo(
        empresa_id,
        cuenta,
        anio,
        mes
    )

    saldo_extracto = (
        float(
            conciliacion.saldo_extracto
            or 0
        )
        if conciliacion
        else 0
    )

    wb = Workbook()

    ws = wb.active
    ws.title = "CONCILIACION"

    _excel_titulo(
        ws,
        "CRV CONSTRUCTORA - CONCILIACIÓN BANCARIA",
        (
            f"Cuenta: {cuenta} · Periodo: {periodo}"
        ),
        4
    )

    _excel_encabezado(
        ws,
        4,
        [
            "Concepto",
            "Sistema",
            "Extracto",
            "Diferencia"
        ]
    )

    ws.cell(5, 1, "Saldo final")
    ws.cell(5, 2, saldo_sistema)
    ws.cell(5, 3, saldo_extracto)
    ws.cell(
        5,
        4,
        saldo_extracto - saldo_sistema
    )

    for col in range(
        2,
        5
    ):
        _excel_moneda(
            ws.cell(
                5,
                col
            )
        )

    _excel_auto_ancho(
        ws
    )

    mov = wb.create_sheet(
        "MOVIMIENTOS"
    )

    headers = [
        "Fecha",
        "Tipo",
        "Tercero",
        "Concepto",
        "Documento",
        "Cuenta",
        "Cuenta destino",
        "Entrada",
        "Salida",
        "Valor",
        "Conciliado"
    ]

    _excel_titulo(
        mov,
        "MOVIMIENTOS DE CONCILIACIÓN",
        f"{cuenta} · {periodo}",
        len(headers)
    )

    _excel_encabezado(
        mov,
        4,
        headers
    )

    for fila, m in enumerate(
        movimientos,
        5
    ):
        impacto = _impacto_bancario_movimiento(
            m,
            cuenta
        )

        valores = [
            m.fecha,
            m.tipo,
            m.nombre_tercero,
            m.concepto,
            (
                m.numero_documento
                or m.numero_soporte
            ),
            m.cuenta,
            m.cuenta_destino,
            max(0, impacto),
            abs(min(0, impacto)),
            abs(impacto),
            (
                "SI"
                if m.revisado
                else "NO"
            )
        ]

        for col, valor in enumerate(
            valores,
            1
        ):
            mov.cell(
                fila,
                col,
                valor
            )

        for col in (
            8,
            9,
            10
        ):
            _excel_moneda(
                mov.cell(
                    fila,
                    col
                )
            )

    mov.freeze_panes = "A5"
    mov.auto_filter.ref = (
        f"A4:"
        f"{get_column_letter(len(headers))}"
        f"{max(4, mov.max_row)}"
    )

    _excel_auto_ancho(
        mov
    )

    return _enviar_excel(
        wb,
        (
            "CRV_conciliacion_"
            f"{cuenta.replace(' ', '_')}_"
            f"{periodo}.xlsx"
        )
    )


__all__ = ['bancos_caja_excel', 'bancos_caja_pdf', 'conciliacion_bancaria_excel', 'conciliacion_bancaria_pdf']
