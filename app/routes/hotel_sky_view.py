import os
from io import BytesIO
from flask import send_file, current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, session, flash
from app.extensions import db
from app.models.empresa_config import EmpresaConfig
from app.models.sede import Sede
from app.models.movimiento import Movimiento
from app.models.hotel_cliente import HotelCliente
from app.models.hotel_venta_accion import HotelVentaAccion
from app.models.hotel_pago_accion import HotelPagoAccion
from app.models.hotel_cuota import HotelCuota
from app.services.empresa_branding import obtener_config_empresa, tomar_siguiente_numero

hotel_sky_view_bp = Blueprint("hotel_sky_view", __name__)
def obtener_logo_path_hotel(config):
    logo_path = None

    # 1. Intentar desde configuración (branding)
    logo_url = getattr(config, "logo_url", None)

    if logo_url and "/static/" in str(logo_url):
        logo_file = str(logo_url).split("/static/")[-1]
        test_path = os.path.join(current_app.root_path, "static", logo_file)
        if os.path.exists(test_path):
            logo_path = test_path

    # 2. Fallbacks específicos del hotel
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


def obtener_total_pagos(venta):
    return sum(float(p.valor_pagado or 0) for p in venta.pagos)


def obtener_monto_financiado_original(venta):
    total_final = float(venta.valor_total_final or 0)
    inicial = float(venta.valor_inicial or 0)
    financiado = total_final - inicial
    return financiado if financiado > 0 else 0


def aplicar_campos_legados_venta(venta):
    if hasattr(venta, "valor_unitario"):
        venta.valor_unitario = float(venta.valor_unitario_lista or 0)

    if hasattr(venta, "valor_total"):
        venta.valor_total = float(venta.valor_total_final or 0)

    if hasattr(venta, "valor_recibido_hoy"):
        venta.valor_recibido_hoy = float(venta.valor_inicial or 0)

    if hasattr(venta, "saldo"):
        venta.saldo = float(venta.saldo_pendiente or 0)


def recalcular_campos_comerciales(venta):
    cantidad = int(venta.cantidad_acciones or 0)
    valor_unitario_lista = float(venta.valor_unitario_lista or 0)
    descuento = float(venta.descuento or 0)

    venta.valor_total_lista = cantidad * valor_unitario_lista

    valor_total_final = venta.valor_total_lista - descuento
    if valor_total_final < 0:
        valor_total_final = 0

    venta.valor_total_final = valor_total_final

    if cantidad > 0:
        venta.valor_unitario_final = valor_total_final / cantidad
    else:
        venta.valor_unitario_final = 0

    if venta.financiado and int(venta.numero_cuotas or 0) > 0:
        monto_financiado = obtener_monto_financiado_original(venta)
        venta.valor_cuota = monto_financiado / int(venta.numero_cuotas or 1) if monto_financiado > 0 else 0
    else:
        venta.valor_cuota = 0

    aplicar_campos_legados_venta(venta)


def recalcular_saldos_venta(venta):
    venta.valor_recibido = obtener_total_pagos(venta)

    saldo = float(venta.valor_total_final or 0) - float(venta.valor_recibido or 0)
    if saldo < 0:
        saldo = 0

    venta.saldo_pendiente = saldo
    venta.recalcular_estado()
    aplicar_campos_legados_venta(venta)


def borrar_movimientos_hotel_por_empresa(empresa_id):
    movimientos = Movimiento.query.filter(
        Movimiento.empresa_id == empresa_id,
        Movimiento.categoria.in_(["VENTA ACCIONES HOTEL", "RECIBO CAJA HOTEL"])
    ).all()

    for movimiento in movimientos:
        db.session.delete(movimiento)

    db.session.flush()


def crear_movimiento_pago_hotel(venta, pago):
    movimiento = Movimiento(
        fecha=pago.fecha,
        tipo="INGRESO",
        categoria="VENTA ACCIONES HOTEL",
        cuenta=pago.entidad_pago if pago.entidad_pago else (pago.forma_pago or ""),
        tercero=venta.cliente,
        valor=float(pago.valor_pagado or 0),
        descripcion=f"HOTEL SKY VIEW RECIBO DE CAJA #{pago.consecutivo_recibo} - Venta #{venta.consecutivo_venta} - {venta.cliente}",
        empresa_id=venta.empresa_id,
        sede_id=venta.sede_id
    )
    db.session.add(movimiento)


def reconstruir_todos_movimientos_hotel(empresa_id):
    borrar_movimientos_hotel_por_empresa(empresa_id)

    ventas = HotelVentaAccion.query.filter_by(empresa_id=empresa_id).order_by(
        HotelVentaAccion.fecha.asc(),
        HotelVentaAccion.id.asc()
    ).all()

    for venta in ventas:
        pagos = HotelPagoAccion.query.filter_by(
            venta_accion_id=venta.id
        ).order_by(
            HotelPagoAccion.fecha.asc(),
            HotelPagoAccion.id.asc()
        ).all()

        for pago in pagos:
            crear_movimiento_pago_hotel(venta, pago)

    db.session.flush()


def reorganizar_consecutivos_ventas_hotel(empresa_id):
    ventas = HotelVentaAccion.query.filter_by(
        empresa_id=empresa_id
    ).order_by(
        HotelVentaAccion.fecha.asc(),
        HotelVentaAccion.id.asc()
    ).all()

    consecutivo = 1
    for venta in ventas:
        venta.consecutivo_venta = consecutivo
        consecutivo += 1

    db.session.flush()


def reorganizar_consecutivos_recibos_hotel(empresa_id):
    pagos = HotelPagoAccion.query.filter_by(
        empresa_id=empresa_id
    ).order_by(
        HotelPagoAccion.fecha.asc(),
        HotelPagoAccion.id.asc()
    ).all()

    consecutivo = 1
    for pago in pagos:
        pago.consecutivo_recibo = consecutivo
        consecutivo += 1

    db.session.flush()


def normalizar_documentos_hotel(empresa_id):
    reorganizar_consecutivos_ventas_hotel(empresa_id)
    reorganizar_consecutivos_recibos_hotel(empresa_id)
    reconstruir_todos_movimientos_hotel(empresa_id)
    db.session.flush()


def generar_cuotas_venta(venta):
    for cuota in venta.cuotas:
        db.session.delete(cuota)
    db.session.flush()

    if not venta.financiado:
        return

    numero_cuotas = int(venta.numero_cuotas or 0)
    fecha_base = venta.fecha_primera_cuota
    monto_financiado = obtener_monto_financiado_original(venta)

    if numero_cuotas <= 0 or not fecha_base or monto_financiado <= 0:
        return

    valor_cuota = monto_financiado / numero_cuotas
    venta.valor_cuota = valor_cuota

    anio = fecha_base.year
    mes = fecha_base.month
    dia = fecha_base.day

    for numero in range(1, numero_cuotas + 1):
        mes_real = mes + (numero - 1)
        anio_real = anio + ((mes_real - 1) // 12)
        mes_real = ((mes_real - 1) % 12) + 1

        try:
            fecha_vencimiento = date(anio_real, mes_real, dia)
        except ValueError:
            if mes_real == 2:
                fecha_vencimiento = date(anio_real, mes_real, 28)
            elif mes_real in [4, 6, 9, 11] and dia > 30:
                fecha_vencimiento = date(anio_real, mes_real, 30)
            else:
                fecha_vencimiento = date(anio_real, mes_real, 28)

        cuota = HotelCuota(
            empresa_id=venta.empresa_id,
            venta_accion_id=venta.id,
            numero_cuota=numero,
            fecha_vencimiento=fecha_vencimiento,
            valor_cuota=valor_cuota,
            valor_pagado=0,
            saldo_cuota=valor_cuota,
            estado="PENDIENTE"
        )
        cuota.recalcular_estado()
        db.session.add(cuota)

    db.session.flush()


def reiniciar_cuotas(venta):
    cuotas = HotelCuota.query.filter_by(
        venta_accion_id=venta.id
    ).order_by(HotelCuota.numero_cuota.asc()).all()

    for cuota in cuotas:
        cuota.valor_pagado = 0
        cuota.saldo_cuota = float(cuota.valor_cuota or 0)
        cuota.recalcular_estado()


def aplicar_pago_a_cuotas(venta, valor_pagado):
    restante = float(valor_pagado or 0)

    cuotas = HotelCuota.query.filter_by(
        venta_accion_id=venta.id
    ).order_by(HotelCuota.numero_cuota.asc()).all()

    ultima_cuota_tocada = None

    for cuota in cuotas:
        if restante <= 0:
            break

        saldo_actual = float(cuota.saldo_cuota or 0)
        if saldo_actual <= 0:
            continue

        abono = restante if restante <= saldo_actual else saldo_actual

        cuota.valor_pagado = float(cuota.valor_pagado or 0) + abono
        cuota.saldo_cuota = saldo_actual - abono
        if cuota.saldo_cuota < 0:
            cuota.saldo_cuota = 0

        cuota.recalcular_estado()
        ultima_cuota_tocada = cuota.numero_cuota
        restante -= abono

    return ultima_cuota_tocada


def asegurar_pago_inicial(venta):
    pagos = HotelPagoAccion.query.filter_by(
        venta_accion_id=venta.id
    ).order_by(
        HotelPagoAccion.fecha.asc(),
        HotelPagoAccion.id.asc()
    ).all()

    pago_inicial = None
    for pago in pagos:
        if pago.cuota_aplicada_numero == 0:
            pago_inicial = pago
            break

    if not pago_inicial and float(venta.valor_inicial or 0) > 0:
        for pago in pagos:
            if (
                pago.fecha == venta.fecha and
                abs(float(pago.valor_pagado or 0) - float(venta.valor_inicial or 0)) < 0.01
            ):
                pago_inicial = pago
                pago_inicial.cuota_aplicada_numero = 0
                break

    if float(venta.valor_inicial or 0) <= 0:
        if pago_inicial:
            db.session.delete(pago_inicial)
            db.session.flush()
        return

    if not pago_inicial:
        pago_inicial = HotelPagoAccion(
            fecha=venta.fecha,
            empresa_id=venta.empresa_id,
            venta_accion_id=venta.id,
            cliente_id=venta.cliente_id,
            consecutivo_recibo=0,
            descripcion=venta.descripcion,
            cantidad_acciones=venta.cantidad_acciones,
            valor_pagado=float(venta.valor_inicial or 0),
            saldo_resultante=0,
            forma_pago=venta.forma_pago,
            entidad_pago=venta.entidad_pago,
            cuenta_destino=venta.cuenta_destino,
            cuota_aplicada_numero=0,
            observacion="PAGO INICIAL"
        )
        db.session.add(pago_inicial)
        db.session.flush()
    else:
        pago_inicial.fecha = venta.fecha
        pago_inicial.descripcion = venta.descripcion
        pago_inicial.cantidad_acciones = venta.cantidad_acciones
        pago_inicial.valor_pagado = float(venta.valor_inicial or 0)
        pago_inicial.forma_pago = venta.forma_pago
        pago_inicial.entidad_pago = venta.entidad_pago
        pago_inicial.cuenta_destino = venta.cuenta_destino
        pago_inicial.cuota_aplicada_numero = 0
        if not pago_inicial.observacion:
            pago_inicial.observacion = "PAGO INICIAL"


def recalcular_plan_y_pagos(venta, recrear_cuotas=False):
    recalcular_campos_comerciales(venta)
    asegurar_pago_inicial(venta)

    if venta.financiado:
        if recrear_cuotas or not venta.cuotas:
            generar_cuotas_venta(venta)

        reiniciar_cuotas(venta)

        pagos = HotelPagoAccion.query.filter_by(
            venta_accion_id=venta.id
        ).order_by(
            HotelPagoAccion.fecha.asc(),
            HotelPagoAccion.id.asc()
        ).all()

        acumulado = 0
        for pago in pagos:
            acumulado += float(pago.valor_pagado or 0)

            if pago.cuota_aplicada_numero == 0:
                pago.saldo_resultante = max(float(venta.valor_total_final or 0) - acumulado, 0)
                continue

            cuota_aplicada = aplicar_pago_a_cuotas(venta, pago.valor_pagado)
            pago.cuota_aplicada_numero = cuota_aplicada
            pago.saldo_resultante = max(float(venta.valor_total_final or 0) - acumulado, 0)

    else:
        for cuota in venta.cuotas:
            db.session.delete(cuota)
        db.session.flush()

        pagos = HotelPagoAccion.query.filter_by(
            venta_accion_id=venta.id
        ).order_by(
            HotelPagoAccion.fecha.asc(),
            HotelPagoAccion.id.asc()
        ).all()

        acumulado = 0
        for pago in pagos:
            acumulado += float(pago.valor_pagado or 0)
            if pago.cuota_aplicada_numero != 0:
                pago.cuota_aplicada_numero = None
            pago.saldo_resultante = max(float(venta.valor_total_final or 0) - acumulado, 0)

    recalcular_saldos_venta(venta)
    normalizar_documentos_hotel(venta.empresa_id)


def construir_alertas_cartera(empresa_id):
    hoy = date.today()
    proximos_7 = hoy + timedelta(days=7)

    cuotas = HotelCuota.query.join(HotelVentaAccion).filter(
        HotelCuota.empresa_id == empresa_id,
        HotelCuota.estado != "PAGADA"
    ).order_by(HotelCuota.fecha_vencimiento.asc(), HotelCuota.numero_cuota.asc()).all()

    alertas_vencidas = []
    alertas_por_vencer = []

    for cuota in cuotas:
        venta = cuota.venta_accion

        item = {
            "cuota_id": cuota.id,
            "venta_id": venta.id,
            "venta_numero": venta.consecutivo_venta,
            "cliente": venta.cliente,
            "identificacion": venta.cliente_identificacion,
            "numero_cuota": cuota.numero_cuota,
            "fecha_vencimiento": cuota.fecha_vencimiento,
            "valor_cuota": float(cuota.valor_cuota or 0),
            "saldo_cuota": float(cuota.saldo_cuota or 0),
            "estado": cuota.estado
        }

        if cuota.fecha_vencimiento < hoy and float(cuota.saldo_cuota or 0) > 0:
            alertas_vencidas.append(item)
        elif hoy <= cuota.fecha_vencimiento <= proximos_7 and float(cuota.saldo_cuota or 0) > 0:
            alertas_por_vencer.append(item)

    ventas = HotelVentaAccion.query.filter_by(empresa_id=empresa_id).all()
    clientes_al_dia = 0

    for venta in ventas:
        if venta.financiado:
            if venta.cuotas and all(float(c.saldo_cuota or 0) <= 0 for c in venta.cuotas):
                clientes_al_dia += 1
        else:
            if float(venta.saldo_pendiente or 0) <= 0:
                clientes_al_dia += 1

    return {
        "vencidas": alertas_vencidas,
        "por_vencer": alertas_por_vencer,
        "al_dia": clientes_al_dia
    }


def construir_resumen_cartera(empresa_id):
    hoy = date.today()

    ventas = HotelVentaAccion.query.filter_by(empresa_id=empresa_id).order_by(
        HotelVentaAccion.fecha.desc(),
        HotelVentaAccion.id.desc()
    ).all()

    cuotas = HotelCuota.query.filter_by(empresa_id=empresa_id).all()

    saldo_total = sum(float(v.saldo_pendiente or 0) for v in ventas)
    cartera_vencida = sum(float(c.saldo_cuota or 0) for c in cuotas if c.fecha_vencimiento < hoy and float(c.saldo_cuota or 0) > 0)
    cartera_por_vencer = sum(float(c.saldo_cuota or 0) for c in cuotas if c.fecha_vencimiento >= hoy and float(c.saldo_cuota or 0) > 0)

    clientes_con_saldo = [v for v in ventas if float(v.saldo_pendiente or 0) > 0]

    return {
        "saldo_total": saldo_total,
        "cartera_vencida": cartera_vencida,
        "cartera_por_vencer": cartera_por_vencer,
        "clientes_con_saldo": clientes_con_saldo,
        "cuotas": cuotas
    }



def _dibujar_chip_resumen(pdf, x, y, w, h, titulo, valor, color_top):
    borde = colors.HexColor("#d9e2ec")

    pdf.setFillColor(colors.white)
    pdf.setStrokeColor(borde)
    pdf.roundRect(x, y - h, w, h, 6 * mm, stroke=1, fill=1)

    pdf.setFillColor(color_top)
    pdf.rect(x, y - 1.5 * mm, w, 1.8 * mm, stroke=0, fill=1)

    pdf.setFillColor(colors.HexColor("#17304f"))
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(x + 6 * mm, y - 12 * mm, titulo)

    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(x + 6 * mm, y - 24 * mm, valor)


@hotel_sky_view_bp.route("/hotel-sky-view/cartera-pdf")
def hotel_cartera_pdf():
    if "usuario" not in session:
        return redirect("/login")
    if not validar_hotel_sky_view():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    config = obtener_config_empresa(empresa_id)

    resumen = construir_resumen_cartera(empresa_id)
    alertas = construir_alertas_cartera(empresa_id)

    ventas_con_saldo = HotelVentaAccion.query.filter(
        HotelVentaAccion.empresa_id == empresa_id,
        HotelVentaAccion.saldo_pendiente > 0
    ).order_by(
        HotelVentaAccion.fecha.desc(),
        HotelVentaAccion.id.desc()
    ).all()

    cuotas_pendientes = HotelCuota.query.join(HotelVentaAccion).filter(
        HotelCuota.empresa_id == empresa_id,
        HotelCuota.estado != "PAGADA"
    ).order_by(
        HotelCuota.fecha_vencimiento.asc(),
        HotelCuota.numero_cuota.asc()
    ).all()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margin_x = 12 * mm
    usable_w = width - (2 * margin_x)
    y = height - 14 * mm

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

    logo_path = obtener_logo_path_hotel(config)

    if logo_path:
        pdf.drawImage(
            ImageReader(logo_path),
            margin_x,
            y - 19 * mm,
            width=23 * mm,
            height=23 * mm,
            preserveAspectRatio=True,
            mask="auto"
        )

    nombre_empresa = getattr(config, "nombre_comercial", None) or "HOTEL SKY VIEW"
    nit = getattr(config, "nit", None) or ""
    ciudad = getattr(config, "ciudad", None) or ""

    pdf.setFillColor(color_texto)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawCentredString(width / 2, y - 5 * mm, nombre_empresa.upper())

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawCentredString(width / 2, y - 12 * mm, "CARTERA DE VENTAS DE ACCIONES")

    pdf.setFont("Helvetica-Bold", 9)
    if nit:
        pdf.drawCentredString(width / 2, y - 18 * mm, f"NIT {nit}")

    if ciudad:
        pdf.drawCentredString(width / 2, y - 23 * mm, ciudad.upper())

    chip_x = width - margin_x - 52 * mm
    chip_y = y - 16 * mm
    pdf.setFillColor(color_gris)
    pdf.roundRect(chip_x, chip_y, 52 * mm, 9 * mm, 3 * mm, stroke=0, fill=1)
    pdf.setFillColor(color_texto)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(chip_x + 4 * mm, chip_y + 3.2 * mm, f"Fecha: {date.today().strftime('%d/%m/%Y')}")

    y -= 33 * mm

    pdf.setStrokeColor(color_borde)
    pdf.setLineWidth(0.6)
    pdf.line(margin_x, y, width - margin_x, y)

    y -= 8 * mm

    chip_w = (usable_w - 10 * mm) / 3
    chip_h = 26 * mm

    _dibujar_chip_resumen(
        pdf, margin_x, y, chip_w, chip_h,
        "Saldo total cartera",
        f"${float(resumen['saldo_total'] or 0):,.0f}",
        color_primario
    )
    _dibujar_chip_resumen(
        pdf, margin_x + chip_w + 5 * mm, y, chip_w, chip_h,
        "Cartera vencida",
        f"${float(resumen['cartera_vencida'] or 0):,.0f}",
        colors.HexColor("#ef4444")
    )
    _dibujar_chip_resumen(
        pdf, margin_x + (chip_w + 5 * mm) * 2, y, chip_w, chip_h,
        "Por vencer",
        f"${float(resumen['cartera_por_vencer'] or 0):,.0f}",
        color_secundario
    )

    y -= 32 * mm

    pdf.setFillColor(color_texto)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(margin_x, y, f"Clientes con saldo: {len(resumen['clientes_con_saldo'])}")
    pdf.drawString(margin_x + 72 * mm, y, f"Cuotas vencidas: {len(alertas['vencidas'])}")
    pdf.drawString(margin_x + 140 * mm, y, f"Clientes al día: {alertas['al_dia']}")

    y -= 8 * mm

    pdf.setFillColor(color_azul)
    pdf.roundRect(margin_x, y - 9 * mm, usable_w, 9 * mm, 3 * mm, stroke=0, fill=1)

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 7.5)
    col_x = [
        margin_x + 2 * mm,
        margin_x + 15 * mm,
        margin_x + 35 * mm,
        margin_x + 86 * mm,
        margin_x + 113 * mm,
        margin_x + 129 * mm,
        margin_x + 151 * mm,
        margin_x + 173 * mm,
        margin_x + 194 * mm,
        margin_x + 210 * mm,
    ]

    headers = ["Venta", "Fecha", "Cliente", "ID", "Acc.", "Final", "Recibido", "Saldo", "Cuotas", "Estado"]
    for xh, text_h in zip(col_x, headers):
        pdf.drawString(xh, y - 6 * mm, text_h)

    y -= 12 * mm

    pdf.setFont("Helvetica", 7.2)
    pdf.setFillColor(color_texto)

    for venta in ventas_con_saldo:
        if y < 35 * mm:
            pdf.showPage()
            y = height - 18 * mm

            pdf.setFillColor(color_azul)
            pdf.roundRect(margin_x, y - 9 * mm, usable_w, 9 * mm, 3 * mm, stroke=0, fill=1)
            pdf.setFillColor(colors.white)
            pdf.setFont("Helvetica-Bold", 7.5)
            for xh, text_h in zip(col_x, headers):
                pdf.drawString(xh, y - 6 * mm, text_h)

            y -= 12 * mm
            pdf.setFont("Helvetica", 7.2)
            pdf.setFillColor(color_texto)

        pdf.drawString(col_x[0], y, f"#{venta.consecutivo_venta}")
        pdf.drawString(col_x[1], y, venta.fecha.strftime("%Y-%m-%d") if venta.fecha else "")
        pdf.drawString(col_x[2], y, (venta.cliente or "")[:25])
        pdf.drawString(col_x[3], y, (venta.cliente_identificacion or "")[:14])
        pdf.drawRightString(col_x[5] - 2 * mm, y, f"{int(venta.cantidad_acciones or 0)}")
        pdf.drawRightString(col_x[6] - 2 * mm, y, f"${float(venta.valor_total_final or 0):,.0f}")
        pdf.drawRightString(col_x[7] - 2 * mm, y, f"${float(venta.valor_recibido or 0):,.0f}")
        pdf.drawRightString(col_x[8] - 2 * mm, y, f"${float(venta.saldo_pendiente or 0):,.0f}")
        pdf.drawRightString(col_x[9] - 4 * mm, y, f"{int(venta.numero_cuotas or 0)}")
        pdf.drawString(col_x[9], y, (venta.estado or "PENDIENTE")[:10])

        pdf.setStrokeColor(color_borde)
        pdf.line(margin_x, y - 3 * mm, width - margin_x, y - 3 * mm)
        y -= 6.5 * mm

    y -= 4 * mm

    if y < 55 * mm:
        pdf.showPage()
        y = height - 20 * mm

    pdf.setFillColor(color_azul)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(margin_x, y, "Detalle de cuotas pendientes")

    y -= 6 * mm

    pdf.setFillColor(color_azul)
    pdf.roundRect(margin_x, y - 9 * mm, usable_w, 9 * mm, 3 * mm, stroke=0, fill=1)

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 7.3)
    col2_x = [
        margin_x + 2 * mm,
        margin_x + 16 * mm,
        margin_x + 77 * mm,
        margin_x + 91 * mm,
        margin_x + 121 * mm,
        margin_x + 149 * mm,
        margin_x + 177 * mm,
    ]
    headers2 = ["Venta", "Cliente", "Cuota", "Vence", "Valor cuota", "Saldo", "Estado"]
    for xh, text_h in zip(col2_x, headers2):
        pdf.drawString(xh, y - 6 * mm, text_h)

    y -= 12 * mm
    pdf.setFillColor(color_texto)
    pdf.setFont("Helvetica", 7.1)

    for cuota in cuotas_pendientes:
        if y < 25 * mm:
            pdf.showPage()
            y = height - 18 * mm

            pdf.setFillColor(color_azul)
            pdf.roundRect(margin_x, y - 9 * mm, usable_w, 9 * mm, 3 * mm, stroke=0, fill=1)
            pdf.setFillColor(colors.white)
            pdf.setFont("Helvetica-Bold", 7.3)
            for xh, text_h in zip(col2_x, headers2):
                pdf.drawString(xh, y - 6 * mm, text_h)
            y -= 12 * mm
            pdf.setFillColor(color_texto)
            pdf.setFont("Helvetica", 7.1)

        venta = cuota.venta_accion
        pdf.drawString(col2_x[0], y, f"#{venta.consecutivo_venta}")
        pdf.drawString(col2_x[1], y, (venta.cliente or "")[:32])
        pdf.drawString(col2_x[2], y, str(cuota.numero_cuota))
        pdf.drawString(col2_x[3], y, cuota.fecha_vencimiento.strftime("%Y-%m-%d") if cuota.fecha_vencimiento else "")
        pdf.drawRightString(col2_x[5] - 3 * mm, y, f"${float(cuota.valor_cuota or 0):,.0f}")
        pdf.drawRightString(col2_x[6] - 5 * mm, y, f"${float(cuota.saldo_cuota or 0):,.0f}")
        pdf.drawString(col2_x[6], y, (cuota.estado or "PENDIENTE")[:10])

        pdf.setStrokeColor(color_borde)
        pdf.line(margin_x, y - 3 * mm, width - margin_x, y - 3 * mm)
        y -= 6.5 * mm

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="hotel_sky_view_cartera.pdf",
        mimetype="application/pdf"
    )
@hotel_sky_view_bp.route("/hotel-sky-view/ventas-pdf")
def hotel_ventas_pdf():
    if "usuario" not in session:
        return redirect("/login")
    if not validar_hotel_sky_view():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    config = obtener_config_empresa(empresa_id)

    ventas = HotelVentaAccion.query.filter_by(
        empresa_id=empresa_id
    ).order_by(
        HotelVentaAccion.fecha.desc(),
        HotelVentaAccion.id.desc()
    ).all()

    total_ventas = sum(float(v.valor_total_final or 0) for v in ventas)
    total_inicial = sum(float(v.valor_inicial or 0) for v in ventas)
    total_saldo = sum(float(v.saldo_pendiente or 0) for v in ventas)
    total_acciones = sum(int(v.cantidad_acciones or 0) for v in ventas)

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

    def truncar(texto, max_chars):
        return str(texto or "")[:max_chars]

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
        pdf_obj.drawCentredString(width / 2, y_top - 12 * mm, "LISTADO DE VENTAS DE ACCIONES")

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
        pdf_obj.drawString(chip_x + 4 * mm, chip_y + 3.2 * mm, f"Fecha: {date.today().strftime('%d/%m/%Y')}")

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
        pdf_obj.setFont("Helvetica-Bold", 15)
        pdf_obj.drawString(x + 6 * mm, y_base - 24 * mm, valor)

    def dibujar_tabla_header(pdf_obj, y_base, headers, col_widths):
        x = margin_x
        h = 10 * mm

        pdf_obj.setFillColor(color_azul)
        pdf_obj.roundRect(margin_x, y_base - h, usable_w, h, 3 * mm, stroke=0, fill=1)

        pdf_obj.setFillColor(colors.white)
        pdf_obj.setFont("Helvetica-Bold", 6.2)

        for i, header in enumerate(headers):
            if i in [4, 8]:
                pdf_obj.drawCentredString(x + (col_widths[i] / 2), y_base - 6.3 * mm, header)
            else:
                pdf_obj.drawString(x + 1.5 * mm, y_base - 6.3 * mm, header)
            x += col_widths[i]

        return y_base - 12 * mm

    y = dibujar_encabezado(pdf)

    chip_w = (usable_w - 10 * mm) / 3
    chip_h = 26 * mm

    dibujar_chip(pdf, margin_x, y, chip_w, chip_h, "Total ventas", f"${total_ventas:,.0f}", color_primario)
    dibujar_chip(pdf, margin_x + chip_w + 5 * mm, y, chip_w, chip_h, "Total inicial", f"${total_inicial:,.0f}", color_secundario)
    dibujar_chip(pdf, margin_x + (chip_w + 5 * mm) * 2, y, chip_w, chip_h, "Saldo pendiente", f"${total_saldo:,.0f}", color_rojo)

    y -= 32 * mm

    pdf.setFillColor(color_texto)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(margin_x, y, f"Ventas registradas: {len(ventas)}")
    pdf.drawString(margin_x + 80 * mm, y, f"Acciones vendidas: {total_acciones}")

    y -= 8 * mm

    headers = ["Venta", "Fecha", "Cliente", "ID", "Acc.", "Valor final", "Inicial", "Saldo", "Estado"]

    # SUMA TOTAL = 184 mm  (cabe dentro de 186 mm útiles)
    col_widths = [
        12 * mm,  # Venta
        20 * mm,  # Fecha
        42 * mm,  # Cliente
        22 * mm,  # ID
        10 * mm,  # Acc.
        20 * mm,  # Valor final
        18 * mm,  # Inicial
        18 * mm,  # Saldo
        22 * mm   # Estado
    ]

    y = dibujar_tabla_header(pdf, y, headers, col_widths)

    row_h = 7.2 * mm

    for venta in ventas:
        if y < 28 * mm:
            pdf.showPage()
            y = dibujar_encabezado(pdf)
            y = dibujar_tabla_header(pdf, y, headers, col_widths)

        estado = (venta.estado or "PENDIENTE").upper()
        if estado == "PAGADA":
            color_estado = color_verde
        elif float(venta.saldo_pendiente or 0) > 0:
            color_estado = color_rojo
        else:
            color_estado = color_texto

        valores = [
            f"#{venta.consecutivo_venta}",
            venta.fecha.strftime("%Y-%m-%d") if venta.fecha else "",
            truncar(venta.cliente, 18),
            truncar(venta.cliente_identificacion, 11),
            str(int(venta.cantidad_acciones or 0)),
            f"${float(venta.valor_total_final or 0):,.0f}",
            f"${float(venta.valor_inicial or 0):,.0f}",
            f"${float(venta.saldo_pendiente or 0):,.0f}",
            truncar(estado, 8)
        ]

        pdf.setStrokeColor(color_borde)
        pdf.setLineWidth(0.4)
        pdf.line(margin_x, y - 2 * mm, width - margin_x, y - 2 * mm)

        x = margin_x

        pdf.setFillColor(color_texto)
        pdf.setFont("Helvetica", 6.4)

        # Venta
        pdf.drawString(x + 1.5 * mm, y, valores[0])
        x += col_widths[0]

        # Fecha
        pdf.drawString(x + 1.2 * mm, y, valores[1])
        x += col_widths[1]

        # Cliente
        pdf.drawString(x + 1.2 * mm, y, valores[2])
        x += col_widths[2]

        # ID
        pdf.drawString(x + 1.2 * mm, y, valores[3])
        x += col_widths[3]

        # Acc.
        pdf.drawCentredString(x + (col_widths[4] / 2), y, valores[4])
        x += col_widths[4]

        # Valor final
        pdf.drawRightString(x + col_widths[5] - 1.5 * mm, y, valores[5])
        x += col_widths[5]

        # Inicial
        pdf.drawRightString(x + col_widths[6] - 1.5 * mm, y, valores[6])
        x += col_widths[6]

        # Saldo
        pdf.drawRightString(x + col_widths[7] - 1.5 * mm, y, valores[7])
        x += col_widths[7]

        # Estado
        pdf.setFillColor(color_estado)
        pdf.setFont("Helvetica-Bold", 6.1)
        pdf.drawCentredString(x + (col_widths[8] / 2), y, valores[8])

        y -= row_h

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="hotel_sky_view_ventas.pdf",
        mimetype="application/pdf"
    )
@hotel_sky_view_bp.route("/hotel-sky-view/movimientos-pdf")
def hotel_movimientos_pdf():
    if "usuario" not in session:
        return redirect("/login")
    if not validar_hotel_sky_view():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    config = obtener_config_empresa(empresa_id)

    mes = request.args.get("mes", "").strip()
    tipo_filtro = request.args.get("tipo", "").strip().upper()
    sede_id = request.args.get("sede_id", "").strip()

    query = Movimiento.query.filter_by(empresa_id=empresa_id)

    if sede_id.isdigit():
        query = query.filter_by(sede_id=int(sede_id))

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

    if tipo_filtro in ["INGRESO", "GASTO"]:
        query = query.filter(Movimiento.tipo == tipo_filtro)

    movimientos = query.order_by(
        Movimiento.fecha.desc(),
        Movimiento.id.desc()
    ).all()

    total_ingresos = sum(
        float(m.valor or 0)
        for m in movimientos
        if str(m.tipo or "").strip().upper() == "INGRESO"
    )

    total_gastos = sum(
        float(m.valor or 0)
        for m in movimientos
        if str(m.tipo or "").strip().upper() == "GASTO"
    )

    total_movimientos = len(movimientos)

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

    def truncar(texto, max_chars):
        return str(texto or "")[:max_chars]

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
        pdf_obj.drawCentredString(width / 2, y_top - 12 * mm, "LISTADO DE MOVIMIENTOS")

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
            f"Fecha: {date.today().strftime('%d/%m/%Y')}"
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
        pdf_obj.setFont("Helvetica-Bold", 15)
        pdf_obj.drawString(x + 6 * mm, y_base - 24 * mm, valor)

    def dibujar_tabla_header(pdf_obj, y_base, headers, col_widths):
        x = margin_x
        h = 10 * mm

        pdf_obj.setFillColor(color_azul)
        pdf_obj.roundRect(margin_x, y_base - h, usable_w, h, 3 * mm, stroke=0, fill=1)

        pdf_obj.setFillColor(colors.white)
        pdf_obj.setFont("Helvetica-Bold", 6.0)

        for i, header in enumerate(headers):
            if i in [0, 1, 6]:
                pdf_obj.drawCentredString(x + (col_widths[i] / 2), y_base - 6.3 * mm, header)
            else:
                pdf_obj.drawString(x + 1.3 * mm, y_base - 6.3 * mm, header)
            x += col_widths[i]

        return y_base - 12 * mm

    y = dibujar_encabezado(pdf)

    chip_w = (usable_w - 10 * mm) / 3
    chip_h = 26 * mm

    dibujar_chip(pdf, margin_x, y, chip_w, chip_h, "Total ingresos", f"${total_ingresos:,.0f}", color_verde)
    dibujar_chip(pdf, margin_x + chip_w + 5 * mm, y, chip_w, chip_h, "Total gastos", f"${total_gastos:,.0f}", color_rojo)
    dibujar_chip(pdf, margin_x + (chip_w + 5 * mm) * 2, y, chip_w, chip_h, "Movimientos", f"{total_movimientos}", color_secundario)

    y -= 32 * mm

    pdf.setFillColor(color_texto)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(margin_x, y, f"Mes: {mes if mes else 'Todos'}")
    pdf.drawString(margin_x + 60 * mm, y, f"Tipo: {tipo_filtro if tipo_filtro else 'Todos'}")

    y -= 8 * mm

    headers = ["Fecha", "Tipo", "Categoría", "Cuenta", "Tercero", "Descripción", "Valor"]

    # Total exacto: 184 mm, cabe dentro de 186 mm útiles
    col_widths = [
        18 * mm,  # Fecha
        15 * mm,  # Tipo
        26 * mm,  # Categoría
        24 * mm,  # Cuenta
        27 * mm,  # Tercero
        50 * mm,  # Descripción
        24 * mm   # Valor
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
            truncar(mov.categoria, 14),
            truncar(mov.cuenta, 14),
            truncar(mov.tercero, 16),
            truncar(mov.descripcion, 34),
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
        pdf.drawString(x + 1.1 * mm, y, valores[2])
        x += col_widths[2]

        # Cuenta
        pdf.drawString(x + 1.1 * mm, y, valores[3])
        x += col_widths[3]

        # Tercero
        pdf.drawString(x + 1.1 * mm, y, valores[4])
        x += col_widths[4]

        # Descripción
        pdf.drawString(x + 1.1 * mm, y, valores[5])
        x += col_widths[5]

        # Valor
        pdf.drawRightString(x + col_widths[6] - 1.5 * mm, y, valores[6])

        y -= row_h

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="hotel_sky_view_movimientos.pdf",
        mimetype="application/pdf"
    )

@hotel_sky_view_bp.route("/hotel-sky-view/dashboard")
def hotel_dashboard():
    if "usuario" not in session:
        return redirect("/login")
    if not validar_hotel_sky_view():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    config = obtener_config_empresa(empresa_id)
    mes = request.args.get("mes", "").strip()

    ventas_query = HotelVentaAccion.query.filter_by(empresa_id=empresa_id)
    pagos_query = HotelPagoAccion.query.filter_by(empresa_id=empresa_id)
    movimientos_query = Movimiento.query.filter_by(empresa_id=empresa_id)

    if mes:
        try:
            anio, numero_mes = mes.split("-")
            anio = int(anio)
            numero_mes = int(numero_mes)

            ventas_query = ventas_query.filter(
                db.extract("year", HotelVentaAccion.fecha) == anio,
                db.extract("month", HotelVentaAccion.fecha) == numero_mes
            )
            pagos_query = pagos_query.filter(
                db.extract("year", HotelPagoAccion.fecha) == anio,
                db.extract("month", HotelPagoAccion.fecha) == numero_mes
            )
            movimientos_query = movimientos_query.filter(
                db.extract("year", Movimiento.fecha) == anio,
                db.extract("month", Movimiento.fecha) == numero_mes
            )
        except ValueError:
            pass

    ventas = ventas_query.order_by(
        HotelVentaAccion.fecha.desc(),
        HotelVentaAccion.id.desc()
    ).all()

    pagos = pagos_query.order_by(
        HotelPagoAccion.fecha.desc(),
        HotelPagoAccion.id.desc()
    ).all()

    movimientos = movimientos_query.order_by(
        Movimiento.fecha.desc(),
        Movimiento.id.desc()
    ).all()

    total_ventas = sum(float(v.valor_total_final or 0) for v in ventas)
    total_recaudado = sum(float(p.valor_pagado or 0) for p in pagos)
    total_saldo = sum(float(v.saldo_pendiente or 0) for v in ventas)
    total_acciones = sum(int(v.cantidad_acciones or 0) for v in ventas)

    total_ingresos = sum(
        float(m.valor or 0)
        for m in movimientos
        if str(m.tipo or "").strip().upper() == "INGRESO"
    )

    total_gastos = sum(
        float(m.valor or 0)
        for m in movimientos
        if str(m.tipo or "").strip().upper() == "GASTO"
    )

    total_utilidad = total_ingresos - total_gastos

    alertas = construir_alertas_cartera(empresa_id)

    return render_template(
        "contabilidad/hotel_sky_view_dashboard.html",
        config=config,
        empresa_nombre=config.nombre_comercial if config and config.nombre_comercial else "HOTEL SKY VIEW",
        mes_actual=mes,
        total_ventas=total_ventas,
        total_recaudado=total_recaudado,
        total_saldo=total_saldo,
        total_acciones=total_acciones,
        total_ingresos=total_ingresos,
        total_gastos=total_gastos,
        total_utilidad=total_utilidad,
        ultimas_ventas=ventas[:8],
        ultimos_pagos=pagos[:8],
        alertas_vencidas=alertas["vencidas"],
        alertas_por_vencer=alertas["por_vencer"],
        clientes_al_dia=alertas["al_dia"]
    )


@hotel_sky_view_bp.route("/hotel-sky-view/ventas")
def hotel_ventas():
    if "usuario" not in session:
        return redirect("/login")
    if not validar_hotel_sky_view():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    config = obtener_config_empresa(empresa_id)
    mes = request.args.get("mes", "").strip()

    query = HotelVentaAccion.query.filter_by(empresa_id=empresa_id)

    if mes:
        try:
            anio, numero_mes = mes.split("-")
            anio = int(anio)
            numero_mes = int(numero_mes)

            query = query.filter(
                db.extract("year", HotelVentaAccion.fecha) == anio,
                db.extract("month", HotelVentaAccion.fecha) == numero_mes
            )
        except ValueError:
            pass

    ventas = query.order_by(HotelVentaAccion.fecha.desc(), HotelVentaAccion.id.desc()).all()

    return render_template(
        "contabilidad/hotel_ventas_acciones.html",
        config=config,
        empresa_nombre=config.nombre_comercial,
        ventas=ventas,
        mes_actual=mes
    )


@hotel_sky_view_bp.route("/hotel-sky-view/cartera")
def hotel_cartera():
    if "usuario" not in session:
        return redirect("/login")
    if not validar_hotel_sky_view():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    config = obtener_config_empresa(empresa_id)

    resumen = construir_resumen_cartera(empresa_id)
    alertas = construir_alertas_cartera(empresa_id)

    cuotas_pendientes = HotelCuota.query.join(HotelVentaAccion).filter(
        HotelCuota.empresa_id == empresa_id,
        HotelCuota.estado != "PAGADA"
    ).order_by(HotelCuota.fecha_vencimiento.asc(), HotelCuota.numero_cuota.asc()).all()

    return render_template(
        "contabilidad/hotel_cartera.html",
        config=config,
        empresa_nombre=config.nombre_comercial,
        saldo_total=resumen["saldo_total"],
        cartera_vencida=resumen["cartera_vencida"],
        cartera_por_vencer=resumen["cartera_por_vencer"],
        clientes_con_saldo=resumen["clientes_con_saldo"],
        cuotas_pendientes=cuotas_pendientes,
        alertas_vencidas=alertas["vencidas"],
        alertas_por_vencer=alertas["por_vencer"],
        clientes_al_dia=alertas["al_dia"]
    )


@hotel_sky_view_bp.route("/hotel-sky-view/pagos/<int:venta_id>")
def hotel_gestionar_pagos(venta_id):
    if "usuario" not in session:
        return redirect("/login")
    if not validar_hotel_sky_view():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    config = obtener_config_empresa(empresa_id)
    venta = HotelVentaAccion.query.get_or_404(venta_id)

    if venta.empresa_id != empresa_id:
        return redirect("/hotel-sky-view/ventas")

    pagos = HotelPagoAccion.query.filter_by(
        venta_accion_id=venta.id
    ).order_by(
        HotelPagoAccion.fecha.desc(),
        HotelPagoAccion.id.desc()
    ).all()

    return render_template(
        "contabilidad/hotel_pagos_venta.html",
        config=config,
        empresa_nombre=config.nombre_comercial,
        venta=venta,
        pagos=pagos
    )


@hotel_sky_view_bp.route("/hotel-sky-view/nueva-venta", methods=["GET", "POST"])
def hotel_nueva_venta():
    if "usuario" not in session:
        return redirect("/login")
    if not validar_hotel_sky_view():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    config = obtener_config_empresa(empresa_id)
    sedes = Sede.query.filter_by(empresa_id=empresa_id).order_by(Sede.nombre.asc()).all()

    if request.method == "POST":
        fecha = datetime.strptime(request.form["fecha"], "%Y-%m-%d").date()

        sede_id_texto = request.form.get("sede_id", "").strip()
        sede_id = int(sede_id_texto) if sede_id_texto.isdigit() else None

        cliente_nombre = request.form.get("cliente", "").strip()
        cliente_identificacion = request.form.get("cliente_identificacion", "").strip()
        cliente_direccion = request.form.get("cliente_direccion", "").strip()
        cliente_telefono = request.form.get("cliente_telefono", "").strip()
        cliente_ciudad = request.form.get("cliente_ciudad", "").strip()
        cliente_correo = request.form.get("cliente_correo", "").strip()

        descripcion = request.form.get("descripcion", "").strip()
        cantidad_acciones = int(request.form.get("cantidad_acciones", "1") or 1)
        valor_unitario_lista = float(request.form.get("valor_unitario_lista", "0") or 0)
        descuento = float(request.form.get("descuento", "0") or 0)
        valor_inicial = float(request.form.get("valor_inicial", "0") or 0)

        financiado = request.form.get("financiado", "").strip() == "SI"
        numero_cuotas = int(request.form.get("numero_cuotas", "0") or 0)

        fecha_primera_cuota_texto = request.form.get("fecha_primera_cuota", "").strip()
        fecha_primera_cuota = None
        if fecha_primera_cuota_texto:
            fecha_primera_cuota = datetime.strptime(fecha_primera_cuota_texto, "%Y-%m-%d").date()

        forma_pago = request.form.get("forma_pago", "").strip()
        entidad_pago = request.form.get("entidad_pago", "").strip()
        cuenta_destino = request.form.get("cuenta_destino", "").strip()
        observacion = request.form.get("observacion", "").strip()

        cliente = None
        if cliente_identificacion:
            cliente = HotelCliente.query.filter_by(
                empresa_id=empresa_id,
                identificacion=cliente_identificacion
            ).first()

        if not cliente:
            cliente = HotelCliente(
                empresa_id=empresa_id,
                nombre=cliente_nombre,
                identificacion=cliente_identificacion if cliente_identificacion else None,
                direccion=cliente_direccion,
                telefono=cliente_telefono,
                ciudad=cliente_ciudad,
                correo=cliente_correo
            )
            db.session.add(cliente)
            db.session.flush()
        else:
            cliente.nombre = cliente_nombre
            cliente.direccion = cliente_direccion
            cliente.telefono = cliente_telefono
            cliente.ciudad = cliente_ciudad
            cliente.correo = cliente_correo

        venta = HotelVentaAccion(
            fecha=fecha,
            empresa_id=empresa_id,
            sede_id=sede_id,
            cliente_id=cliente.id,
            consecutivo_venta=0,
            cliente=cliente.nombre,
            cliente_identificacion=cliente.identificacion,
            cliente_direccion=cliente.direccion,
            cliente_telefono=cliente.telefono,
            cliente_ciudad=cliente.ciudad,
            cliente_correo=cliente.correo,
            descripcion=descripcion,
            cantidad_acciones=cantidad_acciones,
            valor_unitario_lista=valor_unitario_lista,
            descuento=descuento,
            valor_unitario_final=0,
            valor_total_lista=0,
            valor_total_final=0,
            valor_inicial=valor_inicial,
            valor_recibido=0,
            saldo_pendiente=0,
            financiado=financiado,
            numero_cuotas=numero_cuotas if financiado else 0,
            valor_cuota=0,
            fecha_primera_cuota=fecha_primera_cuota if financiado else None,
            forma_pago=forma_pago,
            entidad_pago=entidad_pago,
            cuenta_destino=cuenta_destino,
            observacion=observacion,
            estado="PENDIENTE"
        )

        recalcular_campos_comerciales(venta)
        aplicar_campos_legados_venta(venta)

        db.session.add(venta)
        db.session.flush()

        recalcular_plan_y_pagos(venta, recrear_cuotas=True)
        db.session.commit()

        flash("Venta de acciones registrada correctamente.", "success")
        return redirect("/hotel-sky-view/ventas")

    return render_template(
        "contabilidad/hotel_nueva_venta_accion.html",
        config=config,
        empresa_nombre=config.nombre_comercial,
        sedes=sedes
    )


@hotel_sky_view_bp.route("/hotel-sky-view/editar-venta/<int:venta_id>", methods=["GET", "POST"])
def hotel_editar_venta(venta_id):
    if "usuario" not in session:
        return redirect("/login")
    if not validar_hotel_sky_view():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    config = obtener_config_empresa(empresa_id)
    sedes = Sede.query.filter_by(empresa_id=empresa_id).order_by(Sede.nombre.asc()).all()

    venta = HotelVentaAccion.query.get_or_404(venta_id)
    if venta.empresa_id != empresa_id:
        return redirect("/hotel-sky-view/ventas")

    if request.method == "POST":
        venta.fecha = datetime.strptime(request.form["fecha"], "%Y-%m-%d").date()

        sede_id_texto = request.form.get("sede_id", "").strip()
        venta.sede_id = int(sede_id_texto) if sede_id_texto.isdigit() else None

        cliente_nombre = request.form.get("cliente", "").strip()
        cliente_identificacion = request.form.get("cliente_identificacion", "").strip()
        cliente_direccion = request.form.get("cliente_direccion", "").strip()
        cliente_telefono = request.form.get("cliente_telefono", "").strip()
        cliente_ciudad = request.form.get("cliente_ciudad", "").strip()
        cliente_correo = request.form.get("cliente_correo", "").strip()

        cliente = None
        if cliente_identificacion:
            cliente = HotelCliente.query.filter_by(
                empresa_id=empresa_id,
                identificacion=cliente_identificacion
            ).first()

        if not cliente:
            cliente = HotelCliente(
                empresa_id=empresa_id,
                nombre=cliente_nombre,
                identificacion=cliente_identificacion if cliente_identificacion else None,
                direccion=cliente_direccion,
                telefono=cliente_telefono,
                ciudad=cliente_ciudad,
                correo=cliente_correo
            )
            db.session.add(cliente)
            db.session.flush()
        else:
            cliente.nombre = cliente_nombre
            cliente.direccion = cliente_direccion
            cliente.telefono = cliente_telefono
            cliente.ciudad = cliente_ciudad
            cliente.correo = cliente_correo

        venta.cliente_id = cliente.id
        venta.cliente = cliente.nombre
        venta.cliente_identificacion = cliente.identificacion
        venta.cliente_direccion = cliente.direccion
        venta.cliente_telefono = cliente.telefono
        venta.cliente_ciudad = cliente.ciudad
        venta.cliente_correo = cliente.correo

        venta.descripcion = request.form.get("descripcion", "").strip()
        venta.cantidad_acciones = int(request.form.get("cantidad_acciones", "1") or 1)
        venta.valor_unitario_lista = float(request.form.get("valor_unitario_lista", "0") or 0)
        venta.descuento = float(request.form.get("descuento", "0") or 0)
        venta.valor_inicial = float(request.form.get("valor_inicial", "0") or 0)

        venta.financiado = request.form.get("financiado", "").strip() == "SI"
        venta.numero_cuotas = int(request.form.get("numero_cuotas", "0") or 0)

        fecha_primera_cuota_texto = request.form.get("fecha_primera_cuota", "").strip()
        venta.fecha_primera_cuota = datetime.strptime(fecha_primera_cuota_texto, "%Y-%m-%d").date() if fecha_primera_cuota_texto else None

        venta.forma_pago = request.form.get("forma_pago", "").strip()
        venta.entidad_pago = request.form.get("entidad_pago", "").strip()
        venta.cuenta_destino = request.form.get("cuenta_destino", "").strip()
        venta.observacion = request.form.get("observacion", "").strip()

        recalcular_campos_comerciales(venta)
        aplicar_campos_legados_venta(venta)
        recalcular_plan_y_pagos(venta, recrear_cuotas=True)

        pagos_ordenados = HotelPagoAccion.query.filter_by(
            venta_accion_id=venta.id
        ).order_by(
            HotelPagoAccion.fecha.asc(),
            HotelPagoAccion.id.asc()
        ).all()

        for pago in pagos_ordenados:
            pago.descripcion = venta.descripcion
            pago.cantidad_acciones = venta.cantidad_acciones

        db.session.commit()
        flash("Venta actualizada correctamente.", "success")
        return redirect("/hotel-sky-view/ventas")

    return render_template(
        "contabilidad/hotel_nueva_venta_accion.html",
        config=config,
        empresa_nombre=config.nombre_comercial,
        sedes=sedes,
        venta=venta,
        modo_edicion=True
    )


@hotel_sky_view_bp.route("/hotel-sky-view/eliminar-venta/<int:venta_id>", methods=["POST"])
def hotel_eliminar_venta(venta_id):
    if "usuario" not in session:
        return redirect("/login")
    if not validar_hotel_sky_view():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    venta = HotelVentaAccion.query.get_or_404(venta_id)

    if venta.empresa_id != empresa_id:
        return redirect("/hotel-sky-view/ventas")

    for pago in venta.pagos:
        db.session.delete(pago)

    for cuota in venta.cuotas:
        db.session.delete(cuota)

    db.session.delete(venta)
    db.session.flush()

    normalizar_documentos_hotel(empresa_id)
    db.session.commit()

    flash("Venta eliminada correctamente.", "success")
    return redirect("/hotel-sky-view/ventas")


@hotel_sky_view_bp.route("/hotel-sky-view/abonar/<int:venta_id>", methods=["GET", "POST"])
def hotel_abonar_venta(venta_id):
    if "usuario" not in session:
        return redirect("/login")
    if not validar_hotel_sky_view():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    config = obtener_config_empresa(empresa_id)
    venta = HotelVentaAccion.query.get_or_404(venta_id)

    if venta.empresa_id != empresa_id:
        return redirect("/hotel-sky-view/ventas")

    if request.method == "POST":
        fecha = datetime.strptime(request.form["fecha"], "%Y-%m-%d").date()
        valor_pagado = float(request.form.get("valor_pagado", "0") or 0)
        forma_pago = request.form.get("forma_pago", "").strip()
        entidad_pago = request.form.get("entidad_pago", "").strip()
        cuenta_destino = request.form.get("cuenta_destino", "").strip()
        observacion = request.form.get("observacion", "").strip()

        if valor_pagado <= 0:
            flash("El valor del abono debe ser mayor a cero.", "danger")
            return redirect(f"/hotel-sky-view/abonar/{venta.id}")

        pago = HotelPagoAccion(
            fecha=fecha,
            empresa_id=empresa_id,
            venta_accion_id=venta.id,
            cliente_id=venta.cliente_id,
            consecutivo_recibo=0,
            descripcion=venta.descripcion,
            cantidad_acciones=venta.cantidad_acciones,
            valor_pagado=valor_pagado,
            saldo_resultante=0,
            forma_pago=forma_pago,
            entidad_pago=entidad_pago,
            cuenta_destino=cuenta_destino,
            cuota_aplicada_numero=None,
            observacion=observacion
        )

        db.session.add(pago)
        db.session.flush()

        recalcular_plan_y_pagos(venta, recrear_cuotas=False)
        db.session.commit()

        return redirect(f"/hotel-sky-view/recibo/{pago.id}")

    return render_template(
        "contabilidad/hotel_abonar_venta.html",
        config=config,
        empresa_nombre=config.nombre_comercial,
        venta=venta,
        today=date.today()
    )


@hotel_sky_view_bp.route("/hotel-sky-view/editar-pago/<int:pago_id>", methods=["GET", "POST"])
def hotel_editar_pago(pago_id):
    if "usuario" not in session:
        return redirect("/login")
    if not validar_hotel_sky_view():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    config = obtener_config_empresa(empresa_id)
    pago = HotelPagoAccion.query.get_or_404(pago_id)
    venta = pago.venta_accion

    if pago.empresa_id != empresa_id:
        return redirect("/hotel-sky-view/ventas")

    if request.method == "POST":
        pago.fecha = datetime.strptime(request.form["fecha"], "%Y-%m-%d").date()
        pago.valor_pagado = float(request.form.get("valor_pagado", "0") or 0)
        pago.forma_pago = request.form.get("forma_pago", "").strip()
        pago.entidad_pago = request.form.get("entidad_pago", "").strip()
        pago.cuenta_destino = request.form.get("cuenta_destino", "").strip()
        pago.observacion = request.form.get("observacion", "").strip()

        recalcular_plan_y_pagos(venta, recrear_cuotas=False)
        db.session.commit()

        flash("Pago actualizado correctamente.", "success")
        return redirect(f"/hotel-sky-view/recibo/{pago.id}")

    return render_template(
        "contabilidad/hotel_editar_pago.html",
        config=config,
        empresa_nombre=config.nombre_comercial,
        pago=pago,
        venta=venta
    )


@hotel_sky_view_bp.route("/hotel-sky-view/eliminar-pago/<int:pago_id>", methods=["POST"])
def hotel_eliminar_pago(pago_id):
    if "usuario" not in session:
        return redirect("/login")
    if not validar_hotel_sky_view():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    pago = HotelPagoAccion.query.get_or_404(pago_id)
    venta = pago.venta_accion

    if pago.empresa_id != empresa_id:
        return redirect("/hotel-sky-view/ventas")

    db.session.delete(pago)
    db.session.flush()

    recalcular_plan_y_pagos(venta, recrear_cuotas=False)
    db.session.commit()

    flash("Pago eliminado correctamente.", "success")
    return redirect(f"/hotel-sky-view/pagos/{venta.id}")


@hotel_sky_view_bp.route("/hotel-sky-view/recibo/<int:pago_id>")
def hotel_recibo_caja(pago_id):
    if "usuario" not in session:
        return redirect("/login")
    if not validar_hotel_sky_view():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    config = obtener_config_empresa(empresa_id)

    pago = HotelPagoAccion.query.get_or_404(pago_id)
    venta = pago.venta_accion

    if pago.empresa_id != empresa_id:
        return redirect("/hotel-sky-view/ventas")

    return render_template(
        "contabilidad/hotel_recibo_caja.html",
        config=config,
        empresa_nombre=config.nombre_comercial,
        pago=pago,
        venta=venta
    )


@hotel_sky_view_bp.route("/hotel-sky-view/recibo-pdf/<int:pago_id>")
def hotel_recibo_pdf(pago_id):
    if "usuario" not in session:
        return redirect("/login")
    if not validar_hotel_sky_view():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    config = obtener_config_empresa(empresa_id)

    pago = HotelPagoAccion.query.get_or_404(pago_id)
    venta = pago.venta_accion

    if pago.empresa_id != empresa_id:
        return redirect("/hotel-sky-view/ventas")

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margin_x = 12 * mm
    y = height - 14 * mm

    primary = colors.HexColor(config.color_primario if config and config.color_primario else "#0f3d26")
    dark = colors.HexColor("#0f172a")
    light_gray = colors.HexColor("#f3f4f6")
    border = colors.HexColor("#cfd8df")

    logo_path = None
    if config and config.logo_url:
        if "/static/" in config.logo_url:
            logo_file = config.logo_url.split("/static/")[-1]
            test_path = os.path.join(current_app.root_path, "static", logo_file)
            if os.path.exists(test_path):
                logo_path = test_path

    if not logo_path:
        fallback = os.path.join(current_app.root_path, "static", "logo_hotel_sky_view.png.jpg")
        if os.path.exists(fallback):
            logo_path = fallback

    if logo_path:
        pdf.drawImage(ImageReader(logo_path), margin_x, y - 20 * mm, width=20 * mm, height=20 * mm, preserveAspectRatio=True, mask='auto')

    pdf.setFont("Helvetica-Bold", 18)
    pdf.setFillColor(primary)
    pdf.drawCentredString(width / 2, y - 4 * mm, config.nombre_comercial if config else "HOTEL SKY VIEW")

    pdf.setFont("Helvetica-Bold", 12)
    pdf.setFillColor(dark)
    pdf.drawCentredString(width / 2, y - 10 * mm, "RECIBO DE CAJA")

    pdf.setFont("Helvetica-Bold", 9)
    if config and config.nit:
        pdf.drawCentredString(width / 2, y - 16 * mm, f"NIT {config.nit}")
    if config and config.ciudad:
        pdf.drawCentredString(width / 2, y - 21 * mm, f"{config.ciudad}")

    chip_x = width - 72 * mm
    chip_w = 58 * mm
    chip_h = 8 * mm

    def draw_chip(texto, yy):
        pdf.setFillColor(light_gray)
        pdf.roundRect(chip_x, yy, chip_w, chip_h, 3 * mm, fill=1, stroke=0)
        pdf.setFillColor(dark)
        pdf.setFont("Helvetica-Bold", 8.5)
        pdf.drawString(chip_x + 3 * mm, yy + 2.7 * mm, texto)

    draw_chip(f"Fecha: {pago.fecha.strftime('%d/%m/%Y') if pago.fecha else ''}", y - 7 * mm)
    draw_chip(f"Forma pago: {pago.forma_pago if pago.forma_pago else ''}", y - 17 * mm)
    draw_chip(f"Entidad: {pago.entidad_pago if pago.entidad_pago else ''}", y - 27 * mm)

    y -= 34 * mm

    bar_y = y - 7 * mm
    pdf.setFillColor(primary)
    pdf.rect(margin_x, bar_y, width - 2 * margin_x, 10 * mm, fill=1, stroke=0)

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 8)
    correo = config.correo if config and config.correo else ""
    telefono = config.telefono if config and config.telefono else ""
    bar_text = correo
    if correo and telefono:
        bar_text += " | "
    bar_text += telefono
    pdf.drawString(margin_x + 3 * mm, bar_y + 3.7 * mm, bar_text)

    badge_w = 42 * mm
    badge_h = 7 * mm
    badge_x = width - margin_x - badge_w - 3 * mm
    badge_y = bar_y + 1.5 * mm
    pdf.setFillColor(colors.white)
    pdf.roundRect(badge_x, badge_y, badge_w, badge_h, 3 * mm, fill=1, stroke=0)
    pdf.setFillColor(dark)
    pdf.setFont("Helvetica-Bold", 8.5)
    pdf.drawCentredString(badge_x + badge_w / 2, badge_y + 2.4 * mm, f"RECIBO DE CAJA N° {pago.consecutivo_recibo:02d}")

    y = bar_y - 2 * mm

    def draw_info_row(label, value, yy):
        left_w = 32 * mm
        total_w = width - 2 * margin_x
        right_w = total_w - left_w

        pdf.setStrokeColor(border)
        pdf.setFillColor(colors.HexColor("#f8fafc"))
        pdf.rect(margin_x, yy, left_w, 9 * mm, fill=1, stroke=1)

        pdf.setFillColor(colors.white)
        pdf.rect(margin_x + left_w, yy, right_w, 9 * mm, fill=1, stroke=1)

        pdf.setFillColor(dark)
        pdf.setFont("Helvetica-Bold", 8.5)
        pdf.drawString(margin_x + 3 * mm, yy + 3.2 * mm, label)

        pdf.setFont("Helvetica", 8.5)
        pdf.drawString(margin_x + left_w + 3 * mm, yy + 3.2 * mm, str(value or ""))

    y -= 9 * mm
    draw_info_row("Nombre", venta.cliente, y)
    y -= 9 * mm
    draw_info_row("Identificación", venta.cliente_identificacion, y)
    y -= 9 * mm
    draw_info_row("Dirección", venta.cliente_direccion, y)
    y -= 9 * mm
    draw_info_row("Teléfono", venta.cliente_telefono, y)
    y -= 9 * mm
    draw_info_row("Ciudad", venta.cliente_ciudad, y)

    y -= 12 * mm

    col_widths = [95 * mm, 30 * mm, 24 * mm, 36 * mm]
    headers = ["DESCRIPCIÓN", "ACCIONES", "CUOTA", "VALOR PAGO"]
    x = margin_x

    pdf.setFillColor(primary)
    for i, w in enumerate(col_widths):
        pdf.rect(x, y, w, 9 * mm, fill=1, stroke=1)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 8.5)
        pdf.drawString(x + 2 * mm, y + 3.2 * mm, headers[i])
        pdf.setFillColor(primary)
        x += w

    y -= 9 * mm
    x = margin_x
    valores = [
        pago.descripcion or "",
        str(pago.cantidad_acciones or venta.cantidad_acciones or 0),
        "Inicial" if pago.cuota_aplicada_numero == 0 else (str(pago.cuota_aplicada_numero) if pago.cuota_aplicada_numero else "-"),
        f"${(pago.valor_pagado or 0):,.0f}"
    ]

    for i, w in enumerate(col_widths):
        pdf.setFillColor(colors.white)
        pdf.setStrokeColor(border)
        pdf.rect(x, y, w, 9 * mm, fill=1, stroke=1)
        pdf.setFillColor(dark)
        pdf.setFont("Helvetica-Bold" if i == 3 else "Helvetica", 8.5)
        if i in [1, 2]:
            pdf.drawCentredString(x + w / 2, y + 3.2 * mm, valores[i])
        elif i == 3:
            pdf.drawRightString(x + w - 2 * mm, y + 3.2 * mm, valores[i])
        else:
            pdf.drawString(x + 2 * mm, y + 3.2 * mm, valores[i])
        x += w

    y -= 12 * mm

    resumen = [
        ("Valor total final", f"${(venta.valor_total_final or 0):,.0f}"),
        ("Total recibido", f"${(venta.valor_recibido or 0):,.0f}"),
        ("Saldo pendiente", f"${(venta.saldo_pendiente or 0):,.0f}"),
        ("Total pago recibido", f"${(pago.valor_pagado or 0):,.0f}")
    ]

    for label, value in resumen:
        left_w = 32 * mm
        total_w = width - 2 * margin_x
        right_w = total_w - left_w

        pdf.setFillColor(colors.HexColor("#f8fafc"))
        pdf.rect(margin_x, y, left_w, 9 * mm, fill=1, stroke=1)
        pdf.setFillColor(colors.white)
        pdf.rect(margin_x + left_w, y, right_w, 9 * mm, fill=1, stroke=1)

        pdf.setFillColor(dark)
        pdf.setFont("Helvetica-Bold", 8.5)
        pdf.drawString(margin_x + 3 * mm, y + 3.2 * mm, label)

        pdf.setFont("Helvetica", 8.5)
        pdf.drawString(margin_x + left_w + 3 * mm, y + 3.2 * mm, value)
        y -= 9 * mm

    y -= 3 * mm

    obs_h = 18 * mm
    pdf.setStrokeColor(border)
    pdf.roundRect(margin_x, y - obs_h, width - 2 * margin_x, obs_h, 3 * mm, fill=0, stroke=1)
    pdf.setFillColor(primary)
    pdf.setFont("Helvetica-Bold", 8.5)
    pdf.drawString(margin_x + 3 * mm, y - 4 * mm, "OBSERVACIÓN")

    observacion = pago.observacion or venta.observacion or "Sin observaciones."
    obs_lines = simpleSplit(observacion, "Helvetica", 8.5, width - 2 * margin_x - 8 * mm)
    pdf.setFillColor(dark)
    pdf.setFont("Helvetica", 8.5)
    obs_text_y = y - 10 * mm
    for line in obs_lines[:3]:
        pdf.drawString(margin_x + 4 * mm, obs_text_y, line)
        obs_text_y -= 4.2 * mm

    y -= obs_h + 4 * mm

    pdf.setStrokeColor(border)
    pdf.line(margin_x, y, width - margin_x, y)

    nota = config.texto_legal if config and config.texto_legal else (
        "Este recibo valida y reemplaza la consignación realizada en la fecha descrita inicialmente "
        "a la cuenta de ahorros BANCOLOMBIA N° 718-000020-23 a nombre de CRV CONSTRUCCIONES Y URBANIZACIONES SAS."
    )

    nota_lineas = simpleSplit("NOTA ACLARATORIA: " + nota, "Helvetica", 7.8, width - 2 * margin_x)
    pdf.setFillColor(dark)
    pdf.setFont("Helvetica", 7.8)
    nota_y = y - 4.5 * mm
    for linea in nota_lineas:
        pdf.drawString(margin_x + 2 * mm, nota_y, linea)
        nota_y -= 3.8 * mm

    y = nota_y - 5 * mm

    firma_y = y
    box_w = (width - 2 * margin_x - 10 * mm) / 3

    x1 = margin_x
    pdf.line(x1, firma_y, x1 + box_w, firma_y)
    pdf.setFont("Helvetica", 8)
    pdf.drawCentredString(x1 + box_w / 2, firma_y - 6, "FIRMA RECIBIDO")
    pdf.drawCentredString(x1 + box_w / 2, firma_y - 15, "CC.")

    x2 = x1 + box_w + 5 * mm
    pdf.line(x2, firma_y, x2 + box_w, firma_y)
    pdf.drawCentredString(x2 + box_w / 2, firma_y - 11, "Elaborado por")

    x3 = x2 + box_w + 5 * mm
    pdf.line(x3, firma_y, x3 + box_w, firma_y)
    pdf.drawCentredString(x3 + box_w / 2, firma_y - 11, "Aprobado por")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    nombre_archivo = f"recibo_caja_hotel_{pago.consecutivo_recibo:02d}.pdf"
    return send_file(buffer, as_attachment=True, download_name=nombre_archivo, mimetype="application/pdf")
