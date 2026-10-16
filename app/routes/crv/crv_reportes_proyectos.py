"""CRV report routes: proyectos."""

from .crv_core import (
    CRVProyecto,
    Paragraph,
    Spacer,
    Workbook,
    _cierre_periodo,
    _enviar_excel,
    _enviar_pdf,
    _excel_auto_ancho,
    _excel_encabezado,
    _excel_moneda,
    _excel_titulo,
    _money_export,
    _movimientos_proyecto,
    _pdf_encabezado_historia,
    _pdf_estilos_crv,
    _pdf_tabla,
    _resumen_cierre_mes,
    _resumen_proyecto,
    crv_bp,
    date,
    db,
    get_column_letter,
    mm,
    proteger_crv,
    request,
    session,
)

@crv_bp.route(
    "/cierre-mensual/pdf"
)
def cierre_mensual_pdf():

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

    resumen = _resumen_cierre_mes(
        empresa_id,
        anio,
        mes
    )

    cierre = _cierre_periodo(
        empresa_id,
        anio,
        mes
    )

    story = []

    _pdf_encabezado_historia(
        story,
        (
            "CRV CONSTRUCTORA - "
            f"CIERRE MENSUAL {periodo}"
        ),
        (
            f"Estado: "
            f"{cierre.estado if cierre else 'ABIERTO'} "
            "· Informe para administración, gerencia y contador"
        )
    )

    story.append(
        Paragraph(
            "Resumen financiero",
            _pdf_estilos_crv()[2]
        )
    )

    story.append(
        _pdf_tabla(
            [
                "Concepto",
                "Valor"
            ],
            [
                [
                    "Ingresos",
                    _money_export(
                        resumen["ingresos"]
                    )
                ],
                [
                    "Compras",
                    _money_export(
                        resumen["compras"]
                    )
                ],
                [
                    "Gastos",
                    _money_export(
                        resumen["gastos"]
                    )
                ],
                [
                    "Resultado",
                    _money_export(
                        resumen["resultado"]
                    )
                ],
                [
                    "CxP pendiente",
                    _money_export(
                        resumen["cxp_pendiente"]
                    )
                ],
                [
                    "CxC pendiente",
                    _money_export(
                        resumen["cxc_pendiente"]
                    )
                ],
                [
                    "Saldo bancos y caja",
                    _money_export(
                        resumen[
                            "saldo_bancos_caja"
                        ]
                    )
                ],
                [
                    "Movimientos sin conciliar",
                    resumen[
                        "movimientos_sin_conciliar"
                    ]
                ],
            ],
            [
                85 * mm,
                45 * mm
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
            "Movimientos del periodo",
            _pdf_estilos_crv()[2]
        )
    )

    filas_mov = []

    for m in resumen["movimientos"]:
        filas_mov.append([
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
            m.cuenta or "",
            m.proyecto or "",
            _money_export(
                m.valor_neto
                or m.valor
                or 0
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
                "Cuenta",
                "Proyecto",
                "Valor",
                "Conciliado"
            ],
            filas_mov,
            [
                20 * mm,
                30 * mm,
                43 * mm,
                52 * mm,
                34 * mm,
                34 * mm,
                27 * mm,
                24 * mm
            ]
        )
    )

    return _enviar_pdf(
        story,
        (
            f"CRV_cierre_mensual_"
            f"{periodo}.pdf"
        )
    )


@crv_bp.route(
    "/cierre-mensual/excel"
)
def cierre_mensual_excel():

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

    resumen = _resumen_cierre_mes(
        empresa_id,
        anio,
        mes
    )

    cierre = _cierre_periodo(
        empresa_id,
        anio,
        mes
    )

    wb = Workbook()

    ws = wb.active
    ws.title = "CIERRE"

    _excel_titulo(
        ws,
        (
            "CRV CONSTRUCTORA - "
            f"CIERRE {periodo}"
        ),
        (
            "Informe mensual de control contable "
            f"· Estado: "
            f"{cierre.estado if cierre else 'ABIERTO'}"
        ),
        4
    )

    _excel_encabezado(
        ws,
        4,
        [
            "Concepto",
            "Valor",
            "Estado",
            "Observación"
        ]
    )

    filas = [
        (
            "Ingresos",
            resumen["ingresos"],
            "",
            ""
        ),
        (
            "Compras",
            resumen["compras"],
            "",
            ""
        ),
        (
            "Gastos",
            resumen["gastos"],
            "",
            ""
        ),
        (
            "Resultado",
            resumen["resultado"],
            "",
            ""
        ),
        (
            "CxP facturado",
            resumen["cxp_facturado"],
            "",
            ""
        ),
        (
            "CxP pagado",
            resumen["cxp_pagado"],
            "",
            ""
        ),
        (
            "CxP pendiente",
            resumen["cxp_pendiente"],
            "",
            ""
        ),
        (
            "CxC facturado",
            resumen["cxc_facturado"],
            "",
            ""
        ),
        (
            "CxC cobrado",
            resumen["cxc_cobrado"],
            "",
            ""
        ),
        (
            "CxC pendiente",
            resumen["cxc_pendiente"],
            "",
            ""
        ),
        (
            "Saldo bancos y caja al cierre",
            resumen["saldo_bancos_caja"],
            "",
            ""
        ),
        (
            "Movimientos del mes",
            resumen["movimientos_mes"],
            "",
            ""
        ),
        (
            "Movimientos sin conciliar",
            resumen[
                "movimientos_sin_conciliar"
            ],
            (
                "OK"
                if resumen[
                    "movimientos_sin_conciliar"
                ] == 0
                else "PENDIENTE"
            ),
            ""
        ),
    ]

    fila_excel = 5

    for concepto, valor, estado, nota in filas:
        ws.cell(
            fila_excel,
            1,
            concepto
        )

        ws.cell(
            fila_excel,
            2,
            valor
        )

        ws.cell(
            fila_excel,
            3,
            estado
        )

        ws.cell(
            fila_excel,
            4,
            nota
        )

        if concepto not in (
            "Movimientos del mes",
            "Movimientos sin conciliar",
        ):
            _excel_moneda(
                ws.cell(
                    fila_excel,
                    2
                )
            )

        fila_excel += 1

    _excel_auto_ancho(
        ws
    )

    mov_ws = wb.create_sheet(
        "MOVIMIENTOS"
    )

    headers = [
        "Fecha",
        "Tipo",
        "Tercero",
        "Documento",
        "Concepto",
        "Cuenta",
        "Cuenta destino",
        "Proyecto",
        "Centro costo",
        "Valor",
        "Conciliado"
    ]

    _excel_titulo(
        mov_ws,
        f"MOVIMIENTOS DEL PERIODO {periodo}",
        "Detalle utilizado para el cierre mensual",
        len(headers)
    )

    _excel_encabezado(
        mov_ws,
        4,
        headers
    )

    for fila, m in enumerate(
        resumen["movimientos"],
        5
    ):
        valores = [
            m.fecha,
            m.tipo,
            m.nombre_tercero,
            (
                m.numero_documento
                or m.numero_soporte
            ),
            m.concepto,
            m.cuenta,
            m.cuenta_destino,
            m.proyecto,
            m.centro_costo,
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
        f"{get_column_letter(len(headers))}"
        f"{max(4, mov_ws.max_row)}"
    )

    _excel_auto_ancho(
        mov_ws
    )

    bank_ws = wb.create_sheet(
        "SALDOS_BANCOS_CAJA"
    )

    _excel_titulo(
        bank_ws,
        f"SALDOS FINANCIEROS AL {resumen['fecha_fin'].strftime('%d/%m/%Y')}",
        "Saldos calculados de cuentas propias de CRV",
        2
    )

    _excel_encabezado(
        bank_ws,
        4,
        [
            "Cuenta CRV",
            "Saldo"
        ]
    )

    for fila, (
        nombre,
        saldo
    ) in enumerate(
        sorted(
            resumen[
                "saldos_cuentas"
            ].items()
        ),
        5
    ):
        bank_ws.cell(
            fila,
            1,
            nombre
        )

        bank_ws.cell(
            fila,
            2,
            saldo
        )

        _excel_moneda(
            bank_ws.cell(
                fila,
                2
            )
        )

    _excel_auto_ancho(
        bank_ws
    )

    return _enviar_excel(
        wb,
        (
            f"CRV_cierre_mensual_"
            f"{periodo}.xlsx"
        )
    )


@crv_bp.route(
    "/proyectos/pdf"
)
def proyectos_pdf_crv():

    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get(
        "empresa_id"
    )

    proyectos = (
        CRVProyecto.query
        .filter_by(
            empresa_id=empresa_id
        )
        .order_by(
            CRVProyecto.nombre.asc()
        )
        .all()
    )

    story = []

    _pdf_encabezado_historia(
        story,
        "CRV CONSTRUCTORA - PROYECTOS Y OBRAS",
        (
            "Informe financiero consolidado por proyecto "
            f"· Generado {date.today().strftime('%d/%m/%Y')}"
        )
    )

    filas = []

    for proyecto in proyectos:
        resumen = _resumen_proyecto(
            proyecto
        )

        filas.append([
            proyecto.codigo,
            proyecto.nombre,
            proyecto.estado,
            _money_export(
                proyecto.presupuesto
            ),
            _money_export(
                resumen["ingresos"]
            ),
            _money_export(
                resumen["costos"]
            ),
            _money_export(
                resumen["resultado"]
            ),
            _money_export(
                resumen["cxp_pendiente"]
            ),
            _money_export(
                resumen["cxc_pendiente"]
            )
        ])

    story.append(
        _pdf_tabla(
            [
                "Código",
                "Proyecto",
                "Estado",
                "Presupuesto",
                "Ingresos",
                "Costos",
                "Resultado",
                "CxP pendiente",
                "CxC pendiente"
            ],
            filas,
            [
                20 * mm,
                48 * mm,
                22 * mm,
                28 * mm,
                28 * mm,
                28 * mm,
                28 * mm,
                28 * mm,
                28 * mm
            ]
        )
    )

    return _enviar_pdf(
        story,
        (
            f"CRV_proyectos_obras_"
            f"{date.today().isoformat()}.pdf"
        )
    )


@crv_bp.route(
    "/proyectos/excel"
)
def proyectos_excel_crv():

    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get(
        "empresa_id"
    )

    proyectos = (
        CRVProyecto.query
        .filter_by(
            empresa_id=empresa_id
        )
        .order_by(
            CRVProyecto.nombre.asc()
        )
        .all()
    )

    wb = Workbook()

    ws = wb.active
    ws.title = "PROYECTOS"

    headers = [
        "Código",
        "Proyecto",
        "Estado",
        "Tipo",
        "Cliente",
        "Ubicación",
        "Responsable",
        "Centro costo",
        "Presupuesto",
        "Valor contrato",
        "Ingresos",
        "Compras",
        "Gastos",
        "Costos totales",
        "Resultado",
        "CxP pendiente",
        "CxC pendiente",
        "% presupuesto usado"
    ]

    _excel_titulo(
        ws,
        "CRV CONSTRUCTORA - PROYECTOS Y OBRAS",
        (
            "Control financiero por proyecto "
            f"· Generado {date.today().strftime('%d/%m/%Y')}"
        ),
        len(headers)
    )

    _excel_encabezado(
        ws,
        4,
        headers
    )

    for fila, proyecto in enumerate(
        proyectos,
        5
    ):
        resumen = _resumen_proyecto(
            proyecto
        )

        valores = [
            proyecto.codigo,
            proyecto.nombre,
            proyecto.estado,
            proyecto.tipo,
            (
                proyecto.cliente.razon_social
                if proyecto.cliente
                else ""
            ),
            proyecto.ubicacion,
            proyecto.responsable,
            proyecto.centro_costo,
            float(
                proyecto.presupuesto
                or 0
            ),
            float(
                proyecto.valor_contrato
                or 0
            ),
            resumen["ingresos"],
            resumen["compras"],
            resumen["gastos"],
            resumen["costos"],
            resumen["resultado"],
            resumen["cxp_pendiente"],
            resumen["cxc_pendiente"],
            resumen["porcentaje_presupuesto"] / 100
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
            9,
            18
        ):
            _excel_moneda(
                ws.cell(
                    fila,
                    col
                )
            )

        ws.cell(
            fila,
            18
        ).number_format = "0.00%"

    ws.freeze_panes = "A5"

    ws.auto_filter.ref = (
        f"A4:"
        f"{get_column_letter(len(headers))}"
        f"{max(4, ws.max_row)}"
    )

    _excel_auto_ancho(
        ws
    )

    detalle = wb.create_sheet(
        "MOVIMIENTOS_PROYECTO"
    )

    headers_detalle = [
        "Proyecto",
        "Fecha",
        "Tipo",
        "Tercero",
        "Documento",
        "Concepto",
        "Cuenta",
        "Centro costo",
        "Valor"
    ]

    _excel_titulo(
        detalle,
        "DETALLE DE MOVIMIENTOS POR PROYECTO",
        "Trazabilidad contable de proyectos y obras",
        len(headers_detalle)
    )

    _excel_encabezado(
        detalle,
        4,
        headers_detalle
    )

    fila = 5

    for proyecto in proyectos:

        for movimiento in _movimientos_proyecto(
            empresa_id,
            proyecto.nombre
        ):

            valores = [
                proyecto.nombre,
                movimiento.fecha,
                movimiento.tipo,
                movimiento.nombre_tercero,
                (
                    movimiento.numero_documento
                    or movimiento.numero_soporte
                ),
                movimiento.concepto,
                movimiento.cuenta,
                movimiento.centro_costo,
                float(
                    movimiento.valor_neto
                    or movimiento.valor
                    or 0
                )
            ]

            for col, valor in enumerate(
                valores,
                1
            ):
                detalle.cell(
                    fila,
                    col,
                    valor
                )

            _excel_moneda(
                detalle.cell(
                    fila,
                    9
                )
            )

            fila += 1

    detalle.freeze_panes = "A5"

    detalle.auto_filter.ref = (
        f"A4:"
        f"{get_column_letter(len(headers_detalle))}"
        f"{max(4, detalle.max_row)}"
    )

    _excel_auto_ancho(
        detalle
    )

    db.session.commit()

    return _enviar_excel(
        wb,
        (
            f"CRV_proyectos_obras_"
            f"{date.today().isoformat()}.xlsx"
        )
    )


__all__ = ['cierre_mensual_excel', 'cierre_mensual_pdf', 'proyectos_excel_crv', 'proyectos_pdf_crv']
