import os
from io import BytesIO
from datetime import date

from flask import Blueprint, render_template, request, redirect, session, send_file, current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

from app.extensions import db
from app.models.empresa_config import EmpresaConfig
from app.models.movimiento import Movimiento
from app.models.hotel_venta_accion import HotelVentaAccion
from app.models.hotel_pago_accion import HotelPagoAccion
from app.models.hotel_cuota import HotelCuota
from app.services.empresa_branding import obtener_config_empresa
from reportlab.pdfgen import canvas


hotel_cierre_bp = Blueprint("hotel_cierre", __name__)


def obtener_logo_path_hotel(config):
    logo_path = None

    logo_url = getattr(config, "logo_url", None)

    if logo_url and "/static/" in str(logo_url):
        logo_file = str(logo_url).split("/static/")[-1]
        test_path = os.path.join(current_app.root_path, "static", logo_file)
        if os.path.exists(test_path):
            logo_path = test_path

    posibles = [
        os.path.join(current_app.root_path, "static", "logo_hotel_sky_view.png"),
        os.path.join(current_app.root_path, "static", "logo_hotel_sky_view.png.jpg"),
        os.path.join(current_app.root_path, "static", "logo_crv.png"),
    ]

    if not logo_path:
        for ruta in posibles:
            if os.path.exists(ruta):
                logo_path = ruta
                break

    return logo_path


def validar_hotel_sky_view():
    if "usuario" not in session:
        return False
    if "empresa_id" not in session:
        return False

    empresa_id = session.get("empresa_id")
    config = EmpresaConfig.query.filter_by(empresa_id=empresa_id).first()
    return config is not None and config.tipo_negocio == "HOTEL_ACCIONES"


def truncar(texto, max_chars):
    return str(texto or "")[:max_chars]


def aplicar_filtro_mes(query, modelo_fecha, mes):
    if mes:
        try:
            anio, numero_mes = mes.split("-")
            anio = int(anio)
            numero_mes = int(numero_mes)

            query = query.filter(
                db.extract("year", modelo_fecha) == anio,
                db.extract("month", modelo_fecha) == numero_mes
            )
        except ValueError:
            pass
    return query


def construir_resumen_cierre_mensual(empresa_id, mes=""):
    query_movimientos = Movimiento.query.filter_by(empresa_id=empresa_id)
    query_ventas = HotelVentaAccion.query.filter_by(empresa_id=empresa_id)
    query_pagos = HotelPagoAccion.query.filter_by(empresa_id=empresa_id)
    query_cuotas = HotelCuota.query.filter_by(empresa_id=empresa_id)

    query_movimientos = aplicar_filtro_mes(query_movimientos, Movimiento.fecha, mes)
    query_ventas = aplicar_filtro_mes(query_ventas, HotelVentaAccion.fecha, mes)
    query_pagos = aplicar_filtro_mes(query_pagos, HotelPagoAccion.fecha, mes)
    query_cuotas = aplicar_filtro_mes(query_cuotas, HotelCuota.fecha_vencimiento, mes)

    movimientos = query_movimientos.order_by(
        Movimiento.fecha.desc(),
        Movimiento.id.desc()
    ).all()

    ventas = query_ventas.order_by(
        HotelVentaAccion.fecha.desc(),
        HotelVentaAccion.id.desc()
    ).all()

    pagos = query_pagos.order_by(
        HotelPagoAccion.fecha.desc(),
        HotelPagoAccion.id.desc()
    ).all()

    cuotas = query_cuotas.all()

    ingresos = sum(
        float(m.valor or 0)
        for m in movimientos
        if str(m.tipo or "").strip().upper() == "INGRESO"
    )

    gastos = sum(
        float(m.valor or 0)
        for m in movimientos
        if str(m.tipo or "").strip().upper() == "GASTO"
    )

    utilidad = ingresos - gastos

    total_ventas = sum(float(v.valor_total_final or 0) for v in ventas)
    total_recaudado = sum(float(p.valor_pagado or 0) for p in pagos)
    total_acciones = sum(int(v.cantidad_acciones or 0) for v in ventas)

    cartera_total = sum(float(v.saldo_pendiente or 0) for v in ventas)
    cartera_vencida = sum(
        float(c.saldo_cuota or 0)
        for c in cuotas
        if c.fecha_vencimiento and c.fecha_vencimiento < date.today() and float(c.saldo_cuota or 0) > 0
    )
    cartera_por_vencer = sum(
        float(c.saldo_cuota or 0)
        for c in cuotas
        if c.fecha_vencimiento and c.fecha_vencimiento >= date.today() and float(c.saldo_cuota or 0) > 0
    )

    return {
        "mes": mes,
        "movimientos": movimientos,
        "ingresos": ingresos,
        "gastos": gastos,
        "utilidad": utilidad,
        "total_movimientos": len(movimientos),
        "total_ventas": total_ventas,
        "total_recaudado": total_recaudado,
        "total_acciones": total_acciones,
        "cartera_total": cartera_total,
        "cartera_vencida": cartera_vencida,
        "cartera_por_vencer": cartera_por_vencer,
    }


@hotel_cierre_bp.route("/hotel-sky-view/cierre-mensual")
def hotel_cierre_mensual():
    if "usuario" not in session:
        return redirect("/login")
    if not validar_hotel_sky_view():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    config = obtener_config_empresa(empresa_id)
    mes = request.args.get("mes", "").strip()

    resumen = construir_resumen_cierre_mensual(empresa_id, mes)

    return render_template(
        "contabilidad/hotel_cierre_mensual.html",
        config=config,
        empresa_nombre=config.nombre_comercial if config and config.nombre_comercial else "HOTEL SKY VIEW",
        mes_actual=mes,
        ingresos=resumen["ingresos"],
        gastos=resumen["gastos"],
        utilidad=resumen["utilidad"],
        total_movimientos=resumen["total_movimientos"],
        total_ventas=resumen["total_ventas"],
        total_recaudado=resumen["total_recaudado"],
        total_acciones=resumen["total_acciones"],
        cartera_total=resumen["cartera_total"],
        cartera_vencida=resumen["cartera_vencida"],
        cartera_por_vencer=resumen["cartera_por_vencer"],
        movimientos=resumen["movimientos"]
    )


@hotel_cierre_bp.route("/hotel-sky-view/cierre-mensual-pdf")
def hotel_cierre_mensual_pdf():
    if "usuario" not in session:
        return redirect("/login")
    if not validar_hotel_sky_view():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    config = obtener_config_empresa(empresa_id)
    mes = request.args.get("mes", "").strip()

    resumen = construir_resumen_cierre_mensual(empresa_id, mes)
    movimientos = resumen["movimientos"]

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margin_x = 12 * mm
    usable_w = width - (2 * margin_x)

    color_primario = colors.HexColor(
        config.color_primario if config and getattr(config, "color_primario", None) else "#0f3d26"
    )
    color_secundario = colors.HexColor(
        config.color_secundario if config and getattr(config, "color_secundario", None) else "#d8b541"
    )
    color_azul = colors.HexColor("#17304f")
    color_borde = colors.HexColor("#cfd8df")
    color_gris = colors.HexColor("#f3f4f6")
    color_texto = colors.HexColor("#0f172a")
    color_verde = colors.HexColor("#16a34a")
    color_rojo = colors.HexColor("#ef4444")

    def dibujar_encabezado(pdf_obj):
        y_top = height - 14 * mm

        logo_path = obtener_logo_path_hotel(config)
        if logo_path:
            pdf_obj.drawImage(
                ImageReader(logo_path),
                margin_x,
                y_top - 19 * mm,
                width=23 * mm,
                height=23 * mm,
                preserveAspectRatio=True,
                mask="auto"
            )

        nombre_empresa = getattr(config, "nombre_comercial", None) or "HOTEL SKY VIEW"
        nit = getattr(config, "nit", None) or ""
        ciudad = getattr(config, "ciudad", None) or ""

        pdf_obj.setFillColor(color_texto)
        pdf_obj.setFont("Helvetica-Bold", 18)
        pdf_obj.drawCentredString(width / 2, y_top - 5 * mm, nombre_empresa.upper())

        pdf_obj.setFont("Helvetica-Bold", 12)
        pdf_obj.drawCentredString(width / 2, y_top - 12 * mm, "CIERRE MENSUAL")

        pdf_obj.setFont("Helvetica-Bold", 9)
        if nit:
            pdf_obj.drawCentredString(width / 2, y_top - 18 * mm, f"NIT {nit}")
        if ciudad:
            pdf_obj.drawCentredString(width / 2, y_top - 23 * mm, ciudad.upper())

        chip_x = width - margin_x - 52 * mm
        chip_y = y_top - 16 * mm
        pdf_obj.setFillColor(color_gris)
        pdf_obj.roundRect(chip_x, chip_y, 52 * mm, 9 * mm, 3 * mm, stroke=0, fill=1)
        pdf_obj.setFillColor(color_texto)
        pdf_obj.setFont("Helvetica-Bold", 9)
        pdf_obj.drawString(
            chip_x + 4 * mm,
            chip_y + 3.2 * mm,
            f"Mes: {mes if mes else 'Todos'}"
        )

        y_linea = y_top - 33 * mm
        pdf_obj.setStrokeColor(color_borde)
        pdf_obj.setLineWidth(0.6)
        pdf_obj.line(margin_x, y_linea, width - margin_x, y_linea)

        return y_linea - 8 * mm

    def dibujar_chip(pdf_obj, x, y_base, w, h, titulo, valor, color_top):
        pdf_obj.setFillColor(colors.white)
        pdf_obj.setStrokeColor(color_borde)
        pdf_obj.roundRect(x, y_base - h, w, h, 6 * mm, stroke=1, fill=1)

        pdf_obj.setFillColor(color_top)
        pdf_obj.rect(x, y_base - 1.5 * mm, w, 1.8 * mm, stroke=0, fill=1)

        pdf_obj.setFillColor(color_azul)
        pdf_obj.setFont("Helvetica-Bold", 10)
        pdf_obj.drawString(x + 6 * mm, y_base - 12 * mm, titulo)

        pdf_obj.setFillColor(colors.black)
        pdf_obj.setFont("Helvetica-Bold", 14)
        pdf_obj.drawString(x + 6 * mm, y_base - 24 * mm, valor)

    def dibujar_tabla_header(pdf_obj, y_base, headers, col_widths):
        x = margin_x
        h = 10 * mm

        pdf_obj.setFillColor(color_azul)
        pdf_obj.roundRect(margin_x, y_base - h, usable_w, h, 3 * mm, stroke=0, fill=1)

        pdf_obj.setFillColor(colors.white)
        pdf_obj.setFont("Helvetica-Bold", 6.0)

        for i, header in enumerate(headers):
            if i in [0, 1, 5]:
                pdf_obj.drawCentredString(x + (col_widths[i] / 2), y_base - 6.3 * mm, header)
            else:
                pdf_obj.drawString(x + 1.2 * mm, y_base - 6.3 * mm, header)
            x += col_widths[i]

        return y_base - 12 * mm

    y = dibujar_encabezado(pdf)

    chip_w = (usable_w - 10 * mm) / 3
    chip_h = 26 * mm

    dibujar_chip(pdf, margin_x, y, chip_w, chip_h, "Ingresos", f"${resumen['ingresos']:,.0f}", color_verde)
    dibujar_chip(pdf, margin_x + chip_w + 5 * mm, y, chip_w, chip_h, "Gastos", f"${resumen['gastos']:,.0f}", color_rojo)
    dibujar_chip(pdf, margin_x + (chip_w + 5 * mm) * 2, y, chip_w, chip_h, "Utilidad / Pérdida", f"${resumen['utilidad']:,.0f}", color_secundario)

    y -= 32 * mm

    pdf.setFillColor(color_texto)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(margin_x, y, f"Ventas del mes: ${resumen['total_ventas']:,.0f}")
    pdf.drawString(margin_x + 70 * mm, y, f"Recaudado: ${resumen['total_recaudado']:,.0f}")
    pdf.drawString(margin_x + 138 * mm, y, f"Acciones: {resumen['total_acciones']}")

    y -= 6 * mm
    pdf.drawString(margin_x, y, f"Cartera total: ${resumen['cartera_total']:,.0f}")
    pdf.drawString(margin_x + 70 * mm, y, f"Vencida: ${resumen['cartera_vencida']:,.0f}")
    pdf.drawString(margin_x + 138 * mm, y, f"Por vencer: ${resumen['cartera_por_vencer']:,.0f}")

    y -= 10 * mm

    headers = ["Fecha", "Tipo", "Categoría", "Cuenta", "Descripción", "Valor"]

    col_widths = [
        20 * mm,  # Fecha
        16 * mm,  # Tipo
        32 * mm,  # Categoría
        32 * mm,  # Cuenta
        58 * mm,  # Descripción
        26 * mm   # Valor
    ]

    y = dibujar_tabla_header(pdf, y, headers, col_widths)

    row_h = 7.2 * mm

    for mov in movimientos:
        if y < 28 * mm:
            pdf.showPage()
            y = dibujar_encabezado(pdf)
            y = dibujar_tabla_header(pdf, y, headers, col_widths)

        tipo = str(mov.tipo or "").strip().upper()
        if tipo == "INGRESO":
            color_tipo = color_verde
        elif tipo == "GASTO":
            color_tipo = color_rojo
        else:
            color_tipo = color_texto

        valores = [
            mov.fecha.strftime("%Y-%m-%d") if mov.fecha else "",
            tipo,
            truncar(mov.categoria, 18),
            truncar(mov.cuenta, 18),
            truncar(mov.descripcion, 40),
            f"${float(mov.valor or 0):,.0f}"
        ]

        pdf.setStrokeColor(color_borde)
        pdf.setLineWidth(0.4)
        pdf.line(margin_x, y - 2 * mm, width - margin_x, y - 2 * mm)

        x = margin_x

        pdf.setFillColor(color_texto)
        pdf.setFont("Helvetica", 6.2)

        # Fecha
        pdf.drawCentredString(x + (col_widths[0] / 2), y, valores[0])
        x += col_widths[0]

        # Tipo
        pdf.setFillColor(color_tipo)
        pdf.setFont("Helvetica-Bold", 6.2)
        pdf.drawCentredString(x + (col_widths[1] / 2), y, valores[1])
        x += col_widths[1]

        pdf.setFillColor(color_texto)
        pdf.setFont("Helvetica", 6.2)

        # Categoría
        pdf.drawString(x + 1.2 * mm, y, valores[2])
        x += col_widths[2]

        # Cuenta
        pdf.drawString(x + 1.2 * mm, y, valores[3])
        x += col_widths[3]

        # Descripción
        pdf.drawString(x + 1.2 * mm, y, valores[4])
        x += col_widths[4]

        # Valor
        pdf.drawRightString(x + col_widths[5] - 1.5 * mm, y, valores[5])

        y -= row_h

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="hotel_sky_view_cierre_mensual.pdf",
        mimetype="application/pdf"
    )