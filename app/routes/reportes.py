from io import BytesIO
import os

import pandas as pd
from flask import Blueprint, render_template, request, redirect, session, send_file, current_app
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.extensions import db
from app.models.movimiento import Movimiento
from app.models.sede import Sede
from app.services.empresa_branding import obtener_config_empresa

reportes_bp = Blueprint("reportes", __name__)


COLOR_AZUL = colors.HexColor("#17304f")
COLOR_DORADO = colors.HexColor("#d8b541")
COLOR_BORDE = colors.HexColor("#cfd8df")
COLOR_SUBTITULO = colors.HexColor("#546b87")


def obtener_logo_path_empresa(config):
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


def dibujar_encabezado_reporte_financiero(pdf, config, titulo_reporte, width, height):
    margin_x = 16 * mm
    y_top = height - 18 * mm

    logo_path = obtener_logo_path_empresa(config)
    if logo_path:
        pdf.drawImage(
            ImageReader(logo_path),
            margin_x,
            y_top - 20 * mm,
            width=24 * mm,
            height=24 * mm,
            preserveAspectRatio=True,
            mask="auto"
        )

    nombre_empresa = getattr(config, "razon_social", None) or getattr(config, "nombre_comercial", None) or "EMPRESA"
    nit = getattr(config, "nit", None) or ""
    direccion = getattr(config, "direccion", None) or ""
    ciudad = getattr(config, "ciudad", None) or ""
    telefono = getattr(config, "telefono", None) or ""

    centro_x = width / 2
    texto_y = y_top - 1 * mm

    pdf.setFillColor(COLOR_AZUL)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawCentredString(centro_x, texto_y, nombre_empresa.upper())

    pdf.setFont("Helvetica-Bold", 9)
    if nit:
        pdf.drawCentredString(centro_x, texto_y - 6 * mm, f"NIT: {nit}")

    if direccion:
        pdf.drawCentredString(centro_x, texto_y - 12 * mm, direccion.upper())

    if ciudad:
        pdf.drawCentredString(centro_x, texto_y - 18 * mm, ciudad.upper())

    if telefono:
        pdf.drawCentredString(centro_x, texto_y - 24 * mm, f"TELÉFONO: {telefono}")

    banda_w = 58 * mm
    banda_h = 10 * mm
    banda_x = width - margin_x - banda_w
    banda_y = y_top - 12 * mm

    pdf.setFillColor(COLOR_DORADO)
    pdf.roundRect(banda_x, banda_y, banda_w, banda_h, 4 * mm, fill=1, stroke=0)

    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(banda_x + banda_w / 2, banda_y + 3.2 * mm, "REPORTE FINANCIERO")

    titulo_y = y_top - 35 * mm
    pdf.setFillColor(COLOR_AZUL)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(margin_x, titulo_y, titulo_reporte)

    pdf.setFont("Helvetica", 10)
    pdf.setFillColor(COLOR_SUBTITULO)
    pdf.drawString(margin_x, titulo_y - 6 * mm, "Resumen general de ingresos, gastos y utilidad")

    linea_y = titulo_y - 12 * mm
    pdf.setStrokeColor(COLOR_BORDE)
    pdf.setLineWidth(0.7)
    pdf.line(margin_x, linea_y, width - margin_x, linea_y)

    return linea_y - 10 * mm


def dibujar_resumen_pdf(pdf, x, y, w, h, titulo, valor):
    pdf.setStrokeColor(COLOR_BORDE)
    pdf.setFillColor(colors.white)
    pdf.roundRect(x, y - h, w, h, 10, stroke=1, fill=1)

    pdf.setFillColor(COLOR_DORADO)
    pdf.rect(x, y - 3, w, 3, stroke=0, fill=1)

    pdf.setFillColor(COLOR_AZUL)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(x + 18, y - 22, titulo)

    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(x + 18, y - 42, valor)


def construir_query_movimientos(empresa_id, mes="", tipo_filtro="", sede_id=""):
    movimientos_query = Movimiento.query.filter_by(empresa_id=empresa_id)

    if sede_id.isdigit():
        movimientos_query = movimientos_query.filter_by(sede_id=int(sede_id))

    if mes:
        try:
            anio, numero_mes = mes.split("-")
            anio = int(anio)
            numero_mes = int(numero_mes)

            movimientos_query = movimientos_query.filter(
                db.extract("year", Movimiento.fecha) == anio,
                db.extract("month", Movimiento.fecha) == numero_mes
            )
        except ValueError:
            pass

    if tipo_filtro in ["INGRESO", "GASTO"]:
        movimientos_query = movimientos_query.filter(Movimiento.tipo == tipo_filtro)

    return movimientos_query


def calcular_comparativo_sedes(empresa_id, mes=""):
    sedes = Sede.query.filter_by(empresa_id=empresa_id).order_by(Sede.nombre.asc()).all()
    comparativo = []

    for sede in sedes:
        query = Movimiento.query.filter_by(empresa_id=empresa_id, sede_id=sede.id)

        if mes:
            try:
                anio, numero_mes = mes.split("-")
                anio = int(anio)
                numero_mes = int(numero_mes)

                query = query.filter(
                    db.extract("year", Movimiento.fecha) == anio,
                    db.extract("month", Movimiento.fecha) == numero_mes
                )
            except ValueError:
                pass

        movimientos = query.all()

        ingresos = 0
        gastos = 0

        for m in movimientos:
            tipo = str(m.tipo).strip().upper()
            if tipo == "INGRESO":
                ingresos += m.valor
            elif tipo == "GASTO":
                gastos += m.valor

        utilidad = ingresos - gastos

        comparativo.append({
            "sede": sede.nombre,
            "ingresos": ingresos,
            "gastos": gastos,
            "utilidad": utilidad
        })

    comparativo = sorted(comparativo, key=lambda x: x["utilidad"], reverse=True)
    return comparativo


@reportes_bp.route("/reportes")
def reportes():
    if "usuario" not in session:
        return redirect("/login")

    if "empresa_id" not in session:
        return redirect("/empresas")

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "Empresa")

    mes = request.args.get("mes", "").strip()
    tipo_filtro = request.args.get("tipo", "").strip().upper()
    sede_id = request.args.get("sede_id", "").strip()

    movimientos_query = construir_query_movimientos(
        empresa_id=empresa_id,
        mes=mes,
        tipo_filtro=tipo_filtro,
        sede_id=sede_id
    )

    movimientos = movimientos_query.order_by(Movimiento.fecha.desc()).all()

    ingresos = 0
    gastos = 0
    categorias_ingresos = {}
    categorias_gastos = {}
    cuentas_resumen = {}

    for m in movimientos:
        tipo = str(m.tipo).strip().upper()
        categoria = str(m.categoria).strip()
        cuenta = m.cuenta if m.cuenta else "SIN DEFINIR"

        if tipo == "INGRESO":
            ingresos += m.valor
            categorias_ingresos[categoria] = categorias_ingresos.get(categoria, 0) + m.valor
            cuentas_resumen[cuenta] = cuentas_resumen.get(cuenta, 0) + m.valor
        elif tipo == "GASTO":
            gastos += m.valor
            categorias_gastos[categoria] = categorias_gastos.get(categoria, 0) + m.valor

    utilidad = ingresos - gastos

    ingresos_ordenados = sorted(categorias_ingresos.items(), key=lambda x: x[1], reverse=True)
    gastos_ordenados = sorted(categorias_gastos.items(), key=lambda x: x[1], reverse=True)
    cuentas_ordenadas = sorted(cuentas_resumen.items(), key=lambda x: x[1], reverse=True)

    labels_gastos = [c[0] for c in gastos_ordenados]
    valores_gastos = [c[1] for c in gastos_ordenados]

    sedes = Sede.query.filter_by(empresa_id=empresa_id).order_by(Sede.nombre.asc()).all()
    comparativo_sedes = calcular_comparativo_sedes(empresa_id, mes)

    labels_sedes = [item["sede"] for item in comparativo_sedes]
    ingresos_sedes = [item["ingresos"] for item in comparativo_sedes]
    gastos_sedes = [item["gastos"] for item in comparativo_sedes]
    utilidad_sedes = [item["utilidad"] for item in comparativo_sedes]

    return render_template(
        "contabilidad/reportes.html",
        movimientos=movimientos,
        ingresos=ingresos,
        gastos=gastos,
        utilidad=utilidad,
        categorias_ingresos=ingresos_ordenados,
        categorias_gastos=gastos_ordenados,
        cuentas_resumen=cuentas_ordenadas,
        labels_gastos=labels_gastos,
        valores_gastos=valores_gastos,
        mes_seleccionado=mes,
        tipo_seleccionado=tipo_filtro,
        sede_actual=sede_id,
        sedes=sedes,
        empresa_nombre=empresa_nombre,
        comparativo_sedes=comparativo_sedes,
        labels_sedes=labels_sedes,
        ingresos_sedes=ingresos_sedes,
        gastos_sedes=gastos_sedes,
        utilidad_sedes=utilidad_sedes
    )


@reportes_bp.route("/exportar_excel")
def exportar_excel():
    if "usuario" not in session:
        return redirect("/login")

    if "empresa_id" not in session:
        return redirect("/empresas")

    empresa_id = session.get("empresa_id")

    mes = request.args.get("mes", "").strip()
    tipo_filtro = request.args.get("tipo", "").strip().upper()
    sede_id = request.args.get("sede_id", "").strip()

    movimientos_query = construir_query_movimientos(
        empresa_id=empresa_id,
        mes=mes,
        tipo_filtro=tipo_filtro,
        sede_id=sede_id
    )

    movimientos = movimientos_query.order_by(Movimiento.fecha.desc()).all()

    data = []
    for m in movimientos:
        data.append({
            "Fecha": m.fecha.strftime("%Y-%m-%d") if m.fecha else "",
            "Tipo": m.tipo,
            "Sede": m.sede.nombre if m.sede else "General",
            "Categoría": m.categoria,
            "Cuenta / Medio": m.cuenta if m.cuenta else "",
            "Tercero": m.tercero if m.tercero else "",
            "Valor": m.valor,
            "Descripción": m.descripcion
        })

    df = pd.DataFrame(data)

    output = BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    output.seek(0)

    return send_file(
        output,
        download_name="reporte_movimientos.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@reportes_bp.route("/exportar_pdf")
def exportar_pdf():
    if "usuario" not in session:
        return redirect("/login")

    if "empresa_id" not in session:
        return redirect("/empresas")

    empresa_nombre = session.get("empresa_nombre", "Empresa")
    empresa_id = session.get("empresa_id")
    config = obtener_config_empresa(empresa_id)

    mes = request.args.get("mes", "").strip()
    tipo_filtro = request.args.get("tipo", "").strip().upper()
    sede_id = request.args.get("sede_id", "").strip()

    movimientos_query = construir_query_movimientos(
        empresa_id=empresa_id,
        mes=mes,
        tipo_filtro=tipo_filtro,
        sede_id=sede_id
    )

    sede_nombre = "Todas las sedes"
    if sede_id.isdigit():
        sede = Sede.query.get(int(sede_id))
        if sede:
            sede_nombre = sede.nombre

    movimientos = movimientos_query.order_by(Movimiento.fecha.desc()).all()

    ingresos = sum(m.valor for m in movimientos if str(m.tipo).strip().upper() == "INGRESO")
    gastos = sum(m.valor for m in movimientos if str(m.tipo).strip().upper() == "GASTO")
    utilidad = ingresos - gastos

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y = dibujar_encabezado_reporte_financiero(
        pdf=pdf,
        config=config,
        titulo_reporte=f"{empresa_nombre} - Reporte Financiero",
        width=width,
        height=height
    )

    pdf.setFont("Helvetica", 10)
    pdf.setFillColor(colors.black)
    pdf.drawString(40, y, f"Mes: {mes if mes else 'Todos'}")
    pdf.drawString(220, y, f"Sede: {sede_nombre}")
    pdf.drawString(430, y, f"Tipo: {tipo_filtro if tipo_filtro else 'Todos'}")

    y -= 18
    dibujar_resumen_pdf(pdf, 40, y, 160, 55, "Total ingresos", f"${ingresos:,.0f}")
    dibujar_resumen_pdf(pdf, 220, y, 160, 55, "Total gastos", f"${gastos:,.0f}")
    dibujar_resumen_pdf(pdf, 400, y, 160, 55, "Utilidad / Pérdida", f"${utilidad:,.0f}")

    y -= 82

    pdf.setFillColor(COLOR_AZUL)
    pdf.roundRect(40, y - 22, 530, 22, 8, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(48, y - 14, "Fecha")
    pdf.drawString(100, y - 14, "Tipo")
    pdf.drawString(150, y - 14, "Sede")
    pdf.drawString(220, y - 14, "Cuenta")
    pdf.drawString(320, y - 14, "Valor")
    pdf.drawString(400, y - 14, "Descripción")

    y -= 32
    pdf.setFont("Helvetica", 8)
    pdf.setFillColor(colors.black)

    for m in movimientos:
        if y < 55:
            pdf.showPage()
            y = dibujar_encabezado_reporte_financiero(
                pdf=pdf,
                config=config,
                titulo_reporte=f"{empresa_nombre} - Reporte Financiero",
                width=width,
                height=height
            )
            pdf.setFont("Helvetica", 10)
            pdf.setFillColor(colors.black)
            pdf.drawString(40, y, f"Mes: {mes if mes else 'Todos'}")
            pdf.drawString(220, y, f"Sede: {sede_nombre}")
            pdf.drawString(430, y, f"Tipo: {tipo_filtro if tipo_filtro else 'Todos'}")

            y -= 18
            pdf.setFillColor(COLOR_AZUL)
            pdf.roundRect(40, y - 22, 530, 22, 8, stroke=0, fill=1)
            pdf.setFillColor(colors.white)
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(48, y - 14, "Fecha")
            pdf.drawString(100, y - 14, "Tipo")
            pdf.drawString(150, y - 14, "Sede")
            pdf.drawString(220, y - 14, "Cuenta")
            pdf.drawString(320, y - 14, "Valor")
            pdf.drawString(400, y - 14, "Descripción")
            y -= 32
            pdf.setFont("Helvetica", 8)
            pdf.setFillColor(colors.black)

        pdf.drawString(48, y, m.fecha.strftime("%Y-%m-%d") if m.fecha else "")
        pdf.drawString(100, y, str(m.tipo)[:9] if m.tipo else "")
        pdf.drawString(150, y, (m.sede.nombre if m.sede else "General")[:12])
        pdf.drawString(220, y, (m.cuenta if m.cuenta else "")[:16])
        pdf.drawString(320, y, f"${m.valor:,.0f}")
        pdf.drawString(400, y, (m.descripcion or "")[:30])

        pdf.setStrokeColor(COLOR_BORDE)
        pdf.line(40, y - 5, 570, y - 5)
        y -= 16

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="reporte_financiero.pdf",
        mimetype="application/pdf"
    )


@reportes_bp.route("/exportar_excel_sedes")
def exportar_excel_sedes():
    if "usuario" not in session:
        return redirect("/login")

    if "empresa_id" not in session:
        return redirect("/empresas")

    empresa_id = session.get("empresa_id")
    mes = request.args.get("mes", "").strip()

    comparativo_sedes = calcular_comparativo_sedes(empresa_id, mes)

    df = pd.DataFrame([
        {
            "Sede": item["sede"],
            "Ingresos": item["ingresos"],
            "Gastos": item["gastos"],
            "Utilidad / Pérdida": item["utilidad"]
        }
        for item in comparativo_sedes
    ])

    output = BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    output.seek(0)

    return send_file(
        output,
        download_name="comparativo_sedes.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@reportes_bp.route("/exportar_pdf_sedes")
def exportar_pdf_sedes():
    if "usuario" not in session:
        return redirect("/login")

    if "empresa_id" not in session:
        return redirect("/empresas")

    empresa_nombre = session.get("empresa_nombre", "Empresa")
    empresa_id = session.get("empresa_id")
    config = obtener_config_empresa(empresa_id)
    mes = request.args.get("mes", "").strip()

    comparativo_sedes = calcular_comparativo_sedes(empresa_id, mes)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y = dibujar_encabezado_reporte_financiero(
        pdf=pdf,
        config=config,
        titulo_reporte=f"{empresa_nombre} - Comparativo por Sedes",
        width=width,
        height=height
    )

    pdf.setFont("Helvetica", 10)
    pdf.setFillColor(colors.black)
    pdf.drawString(40, y, f"Mes: {mes if mes else 'Todos'}")
    y -= 18

    pdf.setFillColor(COLOR_AZUL)
    pdf.roundRect(40, y - 22, 520, 22, 8, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(48, y - 14, "Sede")
    pdf.drawString(220, y - 14, "Ingresos")
    pdf.drawString(320, y - 14, "Gastos")
    pdf.drawString(430, y - 14, "Utilidad")

    y -= 32
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(colors.black)

    for item in comparativo_sedes:
        if y < 60:
            pdf.showPage()
            y = dibujar_encabezado_reporte_financiero(
                pdf=pdf,
                config=config,
                titulo_reporte=f"{empresa_nombre} - Comparativo por Sedes",
                width=width,
                height=height
            )
            pdf.setFont("Helvetica", 10)
            pdf.setFillColor(colors.black)
            pdf.drawString(40, y, f"Mes: {mes if mes else 'Todos'}")
            y -= 18

            pdf.setFillColor(COLOR_AZUL)
            pdf.roundRect(40, y - 22, 520, 22, 8, stroke=0, fill=1)
            pdf.setFillColor(colors.white)
            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawString(48, y - 14, "Sede")
            pdf.drawString(220, y - 14, "Ingresos")
            pdf.drawString(320, y - 14, "Gastos")
            pdf.drawString(430, y - 14, "Utilidad")
            y -= 32
            pdf.setFont("Helvetica", 9)
            pdf.setFillColor(colors.black)

        pdf.drawString(48, y, item["sede"][:22])
        pdf.drawString(220, y, f"${item['ingresos']:,.0f}")
        pdf.drawString(320, y, f"${item['gastos']:,.0f}")
        pdf.drawString(430, y, f"${item['utilidad']:,.0f}")

        pdf.setStrokeColor(COLOR_BORDE)
        pdf.line(40, y - 5, 560, y - 5)
        y -= 18

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="comparativo_sedes.pdf",
        mimetype="application/pdf"
    )