from io import BytesIO
import os

import pandas as pd
from flask import Blueprint, render_template, request, redirect, session, send_file, current_app
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from app.extensions import db
from app.models.sede import Sede
from app.models.movimiento import Movimiento
from app.models.venta_ecobike import VentaEcobike
from app.pdf_membrete import dibujar_membrete, COLOR_AZUL, COLOR_BORDE

reportes_ecobike_bp = Blueprint("reportes_ecobike", __name__)


def validar_empresa_ecobike():
    return session.get("empresa_nombre", "").strip().upper() == "ECOBIKE"


def resumen_cierre_sede(empresa_id, sede_id=None, mes=""):
    ventas_query = VentaEcobike.query.filter_by(empresa_id=empresa_id)
    gastos_query = Movimiento.query.filter_by(empresa_id=empresa_id).filter(Movimiento.tipo == "GASTO")

    if sede_id is not None:
        ventas_query = ventas_query.filter_by(sede_id=sede_id)
        gastos_query = gastos_query.filter_by(sede_id=sede_id)

    if mes:
        try:
            anio, numero_mes = mes.split("-")
            anio = int(anio)
            numero_mes = int(numero_mes)

            ventas_query = ventas_query.filter(
                db.extract("year", VentaEcobike.fecha) == anio,
                db.extract("month", VentaEcobike.fecha) == numero_mes
            )

            gastos_query = gastos_query.filter(
                db.extract("year", Movimiento.fecha) == anio,
                db.extract("month", Movimiento.fecha) == numero_mes
            )
        except ValueError:
            pass

    ventas = ventas_query.all()
    gastos = gastos_query.all()

    cantidad_vendida = sum(v.cantidad or 0 for v in ventas)

    venta_contado = 0
    venta_credito = 0
    venta_separado = 0
    recaudo_real = 0
    valor_total_ventas = 0
    costo_importacion = 0

    for v in ventas:
        valor_total = float(v.valor_total or 0)
        valor_recibido = float(v.valor_recibido or 0)
        saldo_pendiente = float(v.saldo_pendiente or 0)
        costo_total = float(v.costo_total or 0)
        tipo_venta = str(v.tipo_venta or "").strip().upper()

        valor_total_ventas += valor_total
        recaudo_real += valor_recibido
        costo_importacion += costo_total

        if tipo_venta == "CONTADO":
            venta_contado += valor_total
        elif tipo_venta == "CREDITO":
            venta_credito += saldo_pendiente
        elif tipo_venta == "SEPARADO":
            venta_separado += saldo_pendiente

    gastos_almacen = sum(float(g.valor or 0) for g in gastos)

    utilidad_operativa = valor_total_ventas - costo_importacion - gastos_almacen
    caja_real = recaudo_real - gastos_almacen

    return {
        "cantidad_vendida": cantidad_vendida,
        "venta_contado": venta_contado,
        "venta_credito": venta_credito,
        "venta_separado": venta_separado,
        "recaudo_real": recaudo_real,
        "valor_total_ventas": valor_total_ventas,
        "gastos_almacen": gastos_almacen,
        "costo_importacion": costo_importacion,
        "utilidad_operativa": utilidad_operativa,
        "caja_real": caja_real
    }


def construir_cierre_por_sedes(empresa_id, mes=""):
    sedes = Sede.query.filter_by(empresa_id=empresa_id).order_by(Sede.nombre.asc()).all()
    filas = []

    for sede in sedes:
        resumen = resumen_cierre_sede(empresa_id, sede.id, mes)
        filas.append({
            "sede": sede.nombre,
            **resumen
        })

    return filas


@reportes_ecobike_bp.route("/ecobike/cierre-mensual")
def cierre_mensual_ecobike():
    if "usuario" not in session:
        return redirect("/login")
    if "empresa_id" not in session:
        return redirect("/empresas")
    if not validar_empresa_ecobike():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "ECOBIKE")

    mes = request.args.get("mes", "").strip()

    cierre_sedes = construir_cierre_por_sedes(empresa_id, mes)
    resumen_general = resumen_cierre_sede(empresa_id, None, mes)

    labels_sedes = [fila["sede"] for fila in cierre_sedes]
    ventas_sedes = [fila["valor_total_ventas"] for fila in cierre_sedes]
    gastos_sedes = [fila["gastos_almacen"] for fila in cierre_sedes]
    utilidad_sedes = [fila["utilidad_operativa"] for fila in cierre_sedes]

    return render_template(
        "contabilidad/cierre_mensual_ecobike.html",
        empresa_nombre=empresa_nombre,
        mes_actual=mes,
        cierre_sedes=cierre_sedes,
        resumen_general=resumen_general,
        labels_sedes=labels_sedes,
        ventas_sedes=ventas_sedes,
        gastos_sedes=gastos_sedes,
        utilidad_sedes=utilidad_sedes
    )


@reportes_ecobike_bp.route("/ecobike/cierre-mensual/excel")
def exportar_excel_cierre_ecobike():
    if "usuario" not in session:
        return redirect("/login")
    if "empresa_id" not in session:
        return redirect("/empresas")
    if not validar_empresa_ecobike():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    mes = request.args.get("mes", "").strip()

    cierre_sedes = construir_cierre_por_sedes(empresa_id, mes)
    resumen_general = resumen_cierre_sede(empresa_id, None, mes)

    data = []
    for fila in cierre_sedes:
        data.append({
            "Sede": fila["sede"],
            "Cantidad vendida": fila["cantidad_vendida"],
            "Venta contado": fila["venta_contado"],
            "Venta crédito": fila["venta_credito"],
            "Venta separado": fila["venta_separado"],
            "Recaudo real": fila["recaudo_real"],
            "Valor total ventas": fila["valor_total_ventas"],
            "Gastos almacén": fila["gastos_almacen"],
            "Costo importación": fila["costo_importacion"],
            "Utilidad operativa": fila["utilidad_operativa"],
            "Caja real": fila["caja_real"]
        })

    data.append({
        "Sede": "TOTAL GENERAL",
        "Cantidad vendida": resumen_general["cantidad_vendida"],
        "Venta contado": resumen_general["venta_contado"],
        "Venta crédito": resumen_general["venta_credito"],
        "Venta separado": resumen_general["venta_separado"],
        "Recaudo real": resumen_general["recaudo_real"],
        "Valor total ventas": resumen_general["valor_total_ventas"],
        "Gastos almacén": resumen_general["gastos_almacen"],
        "Costo importación": resumen_general["costo_importacion"],
        "Utilidad operativa": resumen_general["utilidad_operativa"],
        "Caja real": resumen_general["caja_real"]
    })

    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    output.seek(0)

    return send_file(
        output,
        download_name="cierre_mensual_ecobike.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@reportes_ecobike_bp.route("/ecobike/cierre-mensual/pdf")
def exportar_pdf_cierre_ecobike():
    if "usuario" not in session:
        return redirect("/login")
    if "empresa_id" not in session:
        return redirect("/empresas")
    if not validar_empresa_ecobike():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "ECOBIKE")
    mes = request.args.get("mes", "").strip()

    cierre_sedes = construir_cierre_por_sedes(empresa_id, mes)
    resumen_general = resumen_cierre_sede(empresa_id, None, mes)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=landscape(letter))
    width, height = landscape(letter)

    y = dibujar_membrete(
        pdf,
        current_app,
        empresa_nombre,
        "Cierre Mensual",
        "Resumen gerencial por sedes",
        horizontal=True
    )

    pdf.setFont("Helvetica", 10)
    pdf.setFillColor(colors.black)
    pdf.drawString(34, y, f"Mes: {mes if mes else 'Todos'}")

    y -= 22

    pdf.setFillColor(COLOR_AZUL)
    pdf.roundRect(20, y - 22, 860, 22, 8, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(26, y - 14, "Sede")
    pdf.drawString(110, y - 14, "Vendidas")
    pdf.drawString(170, y - 14, "Contado")
    pdf.drawString(248, y - 14, "Credito")
    pdf.drawString(326, y - 14, "Separado")
    pdf.drawString(410, y - 14, "Recaudo")
    pdf.drawString(492, y - 14, "Venta Total")
    pdf.drawString(587, y - 14, "Gastos")
    pdf.drawString(663, y - 14, "Costo Imp.")
    pdf.drawString(748, y - 14, "Utilidad")
    pdf.drawString(822, y - 14, "Caja")

    y -= 34
    pdf.setFont("Helvetica", 7)
    pdf.setFillColor(colors.black)

    for fila in cierre_sedes:
        if y < 50:
            pdf.showPage()
            y = dibujar_membrete(
                pdf,
                current_app,
                empresa_nombre,
                "Cierre Mensual",
                "Resumen gerencial por sedes",
                horizontal=True
            )
            pdf.setFillColor(COLOR_AZUL)
            pdf.roundRect(20, y - 22, 860, 22, 8, stroke=0, fill=1)
            pdf.setFillColor(colors.white)
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(26, y - 14, "Sede")
            pdf.drawString(110, y - 14, "Vendidas")
            pdf.drawString(170, y - 14, "Contado")
            pdf.drawString(248, y - 14, "Credito")
            pdf.drawString(326, y - 14, "Separado")
            pdf.drawString(410, y - 14, "Recaudo")
            pdf.drawString(492, y - 14, "Venta Total")
            pdf.drawString(587, y - 14, "Gastos")
            pdf.drawString(663, y - 14, "Costo Imp.")
            pdf.drawString(748, y - 14, "Utilidad")
            pdf.drawString(822, y - 14, "Caja")
            y -= 34
            pdf.setFont("Helvetica", 7)
            pdf.setFillColor(colors.black)

        pdf.drawString(26, y, fila["sede"][:14])
        pdf.drawString(110, y, str(fila["cantidad_vendida"]))
        pdf.drawString(170, y, f"${fila['venta_contado']:,.0f}")
        pdf.drawString(248, y, f"${fila['venta_credito']:,.0f}")
        pdf.drawString(326, y, f"${fila['venta_separado']:,.0f}")
        pdf.drawString(410, y, f"${fila['recaudo_real']:,.0f}")
        pdf.drawString(492, y, f"${fila['valor_total_ventas']:,.0f}")
        pdf.drawString(587, y, f"${fila['gastos_almacen']:,.0f}")
        pdf.drawString(663, y, f"${fila['costo_importacion']:,.0f}")
        pdf.drawString(748, y, f"${fila['utilidad_operativa']:,.0f}")
        pdf.drawString(822, y, f"${fila['caja_real']:,.0f}")
        pdf.setStrokeColor(COLOR_BORDE)
        pdf.line(20, y - 4, 880, y - 4)
        y -= 12

    y -= 16
    pdf.setFont("Helvetica-Bold", 8)
    pdf.setFillColor(COLOR_AZUL)
    pdf.drawString(26, y, "TOTAL GENERAL")
    pdf.drawString(110, y, str(resumen_general["cantidad_vendida"]))
    pdf.drawString(170, y, f"${resumen_general['venta_contado']:,.0f}")
    pdf.drawString(248, y, f"${resumen_general['venta_credito']:,.0f}")
    pdf.drawString(326, y, f"${resumen_general['venta_separado']:,.0f}")
    pdf.drawString(410, y, f"${resumen_general['recaudo_real']:,.0f}")
    pdf.drawString(492, y, f"${resumen_general['valor_total_ventas']:,.0f}")
    pdf.drawString(587, y, f"${resumen_general['gastos_almacen']:,.0f}")
    pdf.drawString(663, y, f"${resumen_general['costo_importacion']:,.0f}")
    pdf.drawString(748, y, f"${resumen_general['utilidad_operativa']:,.0f}")
    pdf.drawString(822, y, f"${resumen_general['caja_real']:,.0f}")

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="cierre_mensual_ecobike.pdf",
        mimetype="application/pdf"
    )