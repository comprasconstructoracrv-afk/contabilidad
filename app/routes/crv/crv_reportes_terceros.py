"""CRV report routes: terceros."""

from flask import request

from .crv_core import (
    CRVTercero,
    Workbook,
    _enviar_excel,
    _enviar_pdf,
    _excel_auto_ancho,
    _excel_encabezado,
    _excel_titulo,
    _pdf_encabezado_historia,
    _pdf_tabla,
    crv_bp,
    date,
    db,
    get_column_letter,
    mm,
    proteger_crv,
    session,
)


def _consultar_terceros_reporte(empresa_id):
    """Filtra terceros según el modal seleccionado (?tipo=...) o el buscador (?buscar=...)."""
    tipo = request.args.get("tipo", "").strip().upper()
    busqueda = request.args.get("buscar", "").strip()

    titulos_categoria = {
        "PROVEEDOR": "Proveedores",
        "CLIENTE": "Clientes CRV",
        "CLIENTE_ECOBIKE": "Clientes ECOBIKE",
        "EMPLEADO": "Empleados",
        "EMPLEADO_OBRA": "Empleados de Obra",
        "PASANTE": "Pasantes",
        "CONTRATISTA": "Contratistas",
        "ENTIDAD": "Entidades",
        "TERCERO": "Otros Terceros",
        "ACTIVOS": "Total de Terceros Activos",
    }

    query = CRVTercero.query.filter_by(empresa_id=empresa_id)

    if tipo == "ACTIVOS":
        query = query.filter(CRVTercero.activo.is_(True))
    elif tipo:
        query = query.filter(CRVTercero.tipo_tercero == tipo)

    if busqueda:
        patron = f"%{busqueda}%"
        query = query.filter(
            db.or_(
                CRVTercero.razon_social.ilike(patron),
                CRVTercero.identificacion.ilike(patron),
                CRVTercero.nombre_comercial.ilike(patron),
            )
        )

    terceros = query.order_by(CRVTercero.razon_social.asc()).all()

    etiqueta = titulos_categoria.get(tipo, "Directorio general")
    partes_subtitulo = [etiqueta]
    if busqueda:
        partes_subtitulo.append(f"Búsqueda: '{busqueda}'")
    partes_subtitulo.append(f"{len(terceros)} registros")
    partes_subtitulo.append(f"Generado {date.today().strftime('%d/%m/%Y')}")

    subtitulo = " · ".join(partes_subtitulo)
    slug = f"_{tipo.lower()}" if tipo else ""

    return terceros, subtitulo, slug


@crv_bp.route("/terceros/pdf")
def terceros_pdf():

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    terceros, subtitulo, slug = _consultar_terceros_reporte(empresa_id)

    filas = []

    for t in terceros:
        filas.append([
            t.tipo_tercero or "",
            t.razon_social or "",
            t.identificacion or "",
            (
                t.celular
                or t.telefono
                or ""
            ),
            t.email or "",
            t.ciudad or "",
            t.banco or "",
            (
                "ACTIVO"
                if t.activo
                else "INACTIVO"
            )
        ])

    story = []

    _pdf_encabezado_historia(
        story,
        "CRV CONSTRUCTORA - TERCEROS",
        subtitulo
    )

    story.append(
        _pdf_tabla(
            [
                "Tipo",
                "Nombre / Razón social",
                "NIT/ID",
                "Contacto",
                "Correo",
                "Ciudad",
                "Banco",
                "Estado"
            ],
            filas,
            [
                25 * mm,
                52 * mm,
                28 * mm,
                30 * mm,
                48 * mm,
                28 * mm,
                30 * mm,
                22 * mm
            ]
        )
    )

    return _enviar_pdf(
        story,
        (
            f"CRV_terceros{slug}_"
            f"{date.today().isoformat()}.pdf"
        )
    )


@crv_bp.route("/terceros/excel")
def terceros_excel():

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    terceros, subtitulo, slug = _consultar_terceros_reporte(empresa_id)

    wb = Workbook()
    ws = wb.active
    ws.title = "TERCEROS"

    headers = [
        "Tipo tercero",
        "Tipo documento",
        "Identificación",
        "Razón social",
        "Nombre comercial",
        "Dirección",
        "Ciudad",
        "Departamento",
        "Teléfono",
        "Celular",
        "Email",
        "Contacto",
        "Banco",
        "Tipo cuenta",
        "Número cuenta",
        "Titular cuenta",
        "Estado"
    ]

    _excel_titulo(
        ws,
        "CRV CONSTRUCTORA - TERCEROS",
        subtitulo,
        len(headers)
    )

    _excel_encabezado(
        ws,
        4,
        headers
    )

    for fila, t in enumerate(
        terceros,
        5
    ):
        valores = [
            t.tipo_tercero,
            t.tipo_documento,
            t.identificacion,
            t.razon_social,
            t.nombre_comercial,
            t.direccion,
            t.ciudad,
            t.departamento,
            t.telefono,
            t.celular,
            t.email,
            t.contacto,
            t.banco,
            t.tipo_cuenta,
            t.numero_cuenta,
            t.titular_cuenta,
            "ACTIVO" if t.activo else "INACTIVO"
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
            f"CRV_terceros{slug}_"
            f"{date.today().isoformat()}.xlsx"
        )
    )


__all__ = ['terceros_excel', 'terceros_pdf']