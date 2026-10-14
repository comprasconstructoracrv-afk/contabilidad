from decimal import Decimal
from datetime import datetime
from io import BytesIO
import os

import pandas as pd
from flask import Blueprint, render_template, request, redirect, session, send_file, current_app, flash
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from app.extensions import db
from app.models.sede import Sede
from app.models.producto_ecobike import ProductoEcobike
from app.models.venta_ecobike import VentaEcobike
from app.models.movimiento import Movimiento
from app.models.inventario_ecobike import InventarioEcobike
from app.models.movimiento_inventario_ecobike import MovimientoInventarioEcobike


ventas_ecobike_bp = Blueprint("ventas_ecobike", __name__)


def _descripcion_movimiento_venta(venta):
    referencia = (venta.referencia or "").strip()
    cliente = (venta.cliente or "CLIENTE").strip()
    return f"VENTA ECOBIKE #{venta.id} - {referencia} - {cliente}"


def sincronizar_movimiento_desde_venta(venta):
    descripcion_base = f"VENTA ECOBIKE #{venta.id}"

    movimiento = Movimiento.query.filter(
        Movimiento.descripcion.like(f"{descripcion_base}%")
    ).first()

    valor_ingreso = Decimal(str(venta.valor_recibido or 0))

    if valor_ingreso <= 0:
        if movimiento:
            db.session.delete(movimiento)
        return

    if not movimiento:
        movimiento = Movimiento()
        db.session.add(movimiento)

    movimiento.fecha = venta.fecha
    movimiento.empresa_id = venta.empresa_id
    movimiento.sede_id = venta.sede_id
    movimiento.tipo = "INGRESO"
    movimiento.categoria = "VENTA ECOBIKE"
    movimiento.cuenta = venta.cuenta if venta.cuenta else None
    movimiento.tercero = venta.cliente if venta.cliente else None
    movimiento.descripcion = _descripcion_movimiento_venta(venta)
    movimiento.valor = float(valor_ingreso)

    # =========================================
    # 2. DESCONTAR INVENTARIO (NUEVO)
    # =========================================

    if venta.producto_id:

        inventario = InventarioEcobike.query.filter_by(
            empresa_id=venta.empresa_id,
            producto_id=venta.producto_id,
            sede_id=venta.sede_id if venta.sede_id else None,
            ubicacion="SEDE" if venta.sede_id else "BODEGA"
        ).first()

        if inventario:

            cantidad_anterior = inventario.cantidad
            inventario.cantidad -= venta.cantidad

            if inventario.cantidad < 0:
                inventario.cantidad = 0

            # =========================================
            # 3. REGISTRAR MOVIMIENTO INVENTARIO (KARDEX)
            # =========================================

            mov_inv = MovimientoInventarioEcobike(
                empresa_id=venta.empresa_id,
                producto_id=venta.producto_id,
                sede_origen_id=venta.sede_id if venta.sede_id else None,
                sede_destino_id=None,
                tipo_movimiento="SALIDA",
                cantidad=venta.cantidad,
                observacion=f"Venta #{venta.id} - {venta.cliente}"
            )

            db.session.add(mov_inv)

    # =========================================

def eliminar_movimiento_de_venta(venta_id):
    descripcion_base = f"VENTA ECOBIKE #{venta_id}"
    movimiento = Movimiento.query.filter(
        Movimiento.descripcion.like(f"{descripcion_base}%")
    ).first()

    if movimiento:
        db.session.delete(movimiento)


def validar_empresa_ecobike():
    return session.get("empresa_nombre", "").strip().upper() == "ECOBIKE"


def obtener_logo_path():
    return os.path.join(current_app.root_path, "static", "logo_crv.png")


def dibujar_logo_pdf(pdf, x=40, y=700, ancho=95, alto=60):
    logo_path = obtener_logo_path()
    if os.path.exists(logo_path):
        try:
            pdf.drawImage(
                logo_path,
                x,
                y,
                width=ancho,
                height=alto,
                preserveAspectRatio=True,
                mask="auto"
            )
        except Exception:
            pass


def construir_query_ventas_ecobike(empresa_id, mes="", sede_id="", tipo_venta=""):
    query = VentaEcobike.query.filter_by(empresa_id=empresa_id)

    if sede_id.isdigit():
        query = query.filter_by(sede_id=int(sede_id))

    if tipo_venta in ["CONTADO", "CREDITO", "SEPARADO"]:
        query = query.filter_by(tipo_venta=tipo_venta)

    if mes:
        try:
            anio, numero_mes = mes.split("-")
            anio = int(anio)
            numero_mes = int(numero_mes)

            query = query.filter(
                db.extract("year", VentaEcobike.fecha) == anio,
                db.extract("month", VentaEcobike.fecha) == numero_mes
            )
        except ValueError:
            pass

    return query


def construir_resumen_ventas(ventas):
    total_unidades = 0
    unidades_contado = 0
    unidades_credito = 0
    unidades_separado = 0

    recaudo_real = 0
    valor_credito = 0
    valor_separado = 0
    valor_total_ventas = 0
    costo_total = 0

    cuentas_resumen = {}

    for v in ventas:
        total_unidades += v.cantidad or 0
        recaudo_real += float(v.valor_recibido or 0)
        valor_total_ventas += float(v.valor_total or 0)
        costo_total += float(v.costo_total or 0)

        tipo = str(v.tipo_venta or "").strip().upper()

        if tipo == "CONTADO":
            unidades_contado += v.cantidad or 0

        elif tipo == "CREDITO":
            unidades_credito += v.cantidad or 0
            valor_credito += float(v.saldo_pendiente or 0)

        elif tipo == "SEPARADO":
            unidades_separado += v.cantidad or 0
            valor_separado += float(v.saldo_pendiente or 0)

        cuenta = v.cuenta if v.cuenta else "SIN DEFINIR"
        cuentas_resumen[cuenta] = cuentas_resumen.get(cuenta, 0) + float(v.valor_recibido or 0)

    utilidad_bruta = valor_total_ventas - costo_total
    cuentas_resumen = sorted(cuentas_resumen.items(), key=lambda x: x[1], reverse=True)

    return {
        "total_unidades": total_unidades,
        "unidades_contado": unidades_contado,
        "unidades_credito": unidades_credito,
        "unidades_separado": unidades_separado,
        "recaudo_real": recaudo_real,
        "valor_credito": valor_credito,
        "valor_separado": valor_separado,
        "valor_total_ventas": valor_total_ventas,
        "costo_total": costo_total,
        "utilidad_bruta": utilidad_bruta,
        "cuentas_resumen": cuentas_resumen
    }


def construir_comparativo_sedes(empresa_id, mes=""):
    sedes = Sede.query.filter_by(empresa_id=empresa_id).order_by(Sede.nombre.asc()).all()
    comparativo = []

    for sede in sedes:
        query = VentaEcobike.query.filter_by(empresa_id=empresa_id, sede_id=sede.id)

        if mes:
            try:
                anio, numero_mes = mes.split("-")
                anio = int(anio)
                numero_mes = int(numero_mes)

                query = query.filter(
                    db.extract("year", VentaEcobike.fecha) == anio,
                    db.extract("month", VentaEcobike.fecha) == numero_mes
                )
            except ValueError:
                pass

        ventas = query.all()
        resumen = construir_resumen_ventas(ventas)

        comparativo.append({
            "sede": sede.nombre,
            "unidades": resumen["total_unidades"],
            "recaudo_real": resumen["recaudo_real"],
            "valor_credito": resumen["valor_credito"],
            "valor_separado": resumen["valor_separado"],
            "valor_total_ventas": resumen["valor_total_ventas"],
            "costo_total": resumen["costo_total"],
            "utilidad_bruta": resumen["utilidad_bruta"]
        })

    comparativo = sorted(comparativo, key=lambda x: x["utilidad_bruta"], reverse=True)
    return comparativo


@ventas_ecobike_bp.route("/ventas-ecobike")
def ventas_ecobike():
    if "usuario" not in session:
        return redirect("/login")
    if "empresa_id" not in session:
        return redirect("/empresas")
    if not validar_empresa_ecobike():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "ECOBIKE")

    mes = request.args.get("mes", "").strip()
    sede_id = request.args.get("sede_id", "").strip()
    tipo_venta = request.args.get("tipo_venta", "").strip().upper()

    query = construir_query_ventas_ecobike(
        empresa_id=empresa_id,
        mes=mes,
        sede_id=sede_id,
        tipo_venta=tipo_venta
    )

    ventas = query.order_by(VentaEcobike.fecha.desc(), VentaEcobike.id.desc()).all()
    sedes = Sede.query.filter_by(empresa_id=empresa_id).order_by(Sede.nombre.asc()).all()

    return render_template(
        "contabilidad/ventas_ecobike.html",
        ventas=ventas,
        empresa_nombre=empresa_nombre,
        sedes=sedes,
        sede_actual=sede_id,
        mes_actual=mes,
        tipo_venta_actual=tipo_venta
    )


@ventas_ecobike_bp.route("/ventas-ecobike/nueva", methods=["GET", "POST"])
def nueva_venta_ecobike():
    if "usuario" not in session:
        return redirect("/login")
    if "empresa_id" not in session:
        return redirect("/empresas")
    if not validar_empresa_ecobike():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "ECOBIKE")

    sedes = Sede.query.filter_by(empresa_id=empresa_id).order_by(Sede.nombre.asc()).all()
    productos = ProductoEcobike.query.filter_by(
        empresa_id=empresa_id,
        activo=True
    ).order_by(ProductoEcobike.referencia.asc()).all()

    if request.method == "POST":
        fecha = datetime.strptime(request.form["fecha"], "%Y-%m-%d").date()

        sede_id_texto = request.form.get("sede_id", "").strip()
        sede_id = int(sede_id_texto) if sede_id_texto.isdigit() else None

        producto_id_texto = request.form.get("producto_id", "").strip()
        producto_id = int(producto_id_texto) if producto_id_texto.isdigit() else None

        referencia_manual = request.form.get("referencia_manual", "").strip()
        costo_manual_texto = request.form.get("costo_manual", "").strip()

        cantidad = int(request.form.get("cantidad", "1") or 1)
        precio_unitario = float(request.form.get("precio_unitario", "0") or 0)
        tipo_venta = request.form.get("tipo_venta", "").strip().upper()
        valor_recibido = float(request.form.get("valor_recibido", "0") or 0)
        descuento = float(request.form.get("descuento", "0") or 0)

        cuenta = request.form.get("cuenta", "").strip()
        if cuenta == "OTRO":
            cuenta = request.form.get("otra_cuenta", "").strip()
            if cuenta == "":
                cuenta = "OTRO"

        cliente = request.form.get("cliente", "").strip()
        cliente_cedula = request.form.get("cliente_cedula", "").strip()
        cliente_direccion = request.form.get("cliente_direccion", "").strip()
        cliente_celular = request.form.get("cliente_celular", "").strip()
        cliente_correo = request.form.get("cliente_correo", "").strip()
        observacion = request.form.get("observacion", "").strip()

        costo_manual = float(costo_manual_texto) if costo_manual_texto else None

        if producto_id is None and referencia_manual == "":
            flash("Debe seleccionar una referencia del inventario o escribir una referencia manual.", "danger")
            return redirect("/ventas-ecobike/nueva")

        inventario = None

        if producto_id:
            ubicacion = "SEDE" if sede_id else "BODEGA"

            inventario = InventarioEcobike.query.filter_by(
                empresa_id=empresa_id,
                producto_id=producto_id,
                sede_id=sede_id if sede_id else None,
                ubicacion=ubicacion
            ).first()

            if not inventario:
                flash("No existe inventario para ese producto en la sede/bodega seleccionada.", "danger")
                return redirect("/ventas-ecobike/nueva")

            if int(inventario.cantidad or 0) < cantidad:
                flash(
                    f"Stock insuficiente. Disponible: {inventario.cantidad}, solicitado: {cantidad}.",
                    "danger"
                )
                return redirect("/ventas-ecobike/nueva")

        valor_total = (cantidad * precio_unitario) - descuento
        if valor_total < 0:
            valor_total = 0

        saldo_pendiente = valor_total - valor_recibido
        if saldo_pendiente < 0:
            saldo_pendiente = 0

        nueva_venta = VentaEcobike(
            fecha=fecha,
            empresa_id=empresa_id,
            sede_id=sede_id,
            producto_id=producto_id,
            referencia_manual=referencia_manual if producto_id is None else None,
            costo_manual=costo_manual,
            cantidad=cantidad,
            precio_unitario=precio_unitario,
            tipo_venta=tipo_venta,
            valor_recibido=valor_recibido,
            saldo_pendiente=saldo_pendiente,
            descuento=descuento,
            cuenta=cuenta,
            cliente=cliente,
            cliente_cedula=cliente_cedula,
            cliente_direccion=cliente_direccion,
            cliente_celular=cliente_celular,
            cliente_correo=cliente_correo,
            observacion=observacion
        )

        db.session.add(nueva_venta)
        db.session.flush()

        sincronizar_movimiento_desde_venta(nueva_venta)

        if inventario:
            inventario.cantidad = int(inventario.cantidad or 0) - cantidad

            movimiento_inventario = MovimientoInventarioEcobike(
                empresa_id=empresa_id,
                producto_id=producto_id,
                sede_origen_id=sede_id if sede_id else None,
                sede_destino_id=None,
                tipo_movimiento="VENTA",
                cantidad=cantidad,
                observacion=f"Venta ECOBIKE #{nueva_venta.id} - {cliente or 'Cliente sin nombre'}"
            )
            db.session.add(movimiento_inventario)

        db.session.commit()
        flash("Venta registrada correctamente, ingreso sincronizado e inventario descontado.", "success")
        return redirect("/ventas-ecobike")

    return render_template(
        "contabilidad/nueva_venta_ecobike.html",
        empresa_nombre=empresa_nombre,
        sedes=sedes,
        productos=productos
    )

@ventas_ecobike_bp.route("/ventas-ecobike/editar/<int:id>", methods=["GET", "POST"])
def editar_venta_ecobike(id):
    if "usuario" not in session:
        return redirect("/login")
    if "empresa_id" not in session:
        return redirect("/empresas")
    if not validar_empresa_ecobike():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "ECOBIKE")

    venta = VentaEcobike.query.get_or_404(id)
    if venta.empresa_id != empresa_id:
        return redirect("/ventas-ecobike")

    sedes = Sede.query.filter_by(empresa_id=empresa_id).order_by(Sede.nombre.asc()).all()
    productos = ProductoEcobike.query.filter_by(empresa_id=empresa_id).order_by(ProductoEcobike.referencia.asc()).all()

    if request.method == "POST":
        venta.fecha = datetime.strptime(request.form["fecha"], "%Y-%m-%d").date()

        sede_id_texto = request.form.get("sede_id", "").strip()
        venta.sede_id = int(sede_id_texto) if sede_id_texto.isdigit() else None

        producto_id_texto = request.form.get("producto_id", "").strip()
        producto_id = int(producto_id_texto) if producto_id_texto.isdigit() else None

        referencia_manual = request.form.get("referencia_manual", "").strip()
        costo_manual_texto = request.form.get("costo_manual", "").strip()

        venta.producto_id = producto_id
        venta.referencia_manual = referencia_manual if producto_id is None else None
        venta.costo_manual = float(costo_manual_texto) if costo_manual_texto else None

        venta.cantidad = int(request.form.get("cantidad", "1"))
        venta.precio_unitario = float(request.form.get("precio_unitario", "0"))
        venta.tipo_venta = request.form.get("tipo_venta", "").strip().upper()
        venta.valor_recibido = float(request.form.get("valor_recibido", "0") or 0)
        venta.descuento = float(request.form.get("descuento", "0") or 0)

        valor_total = (venta.cantidad * venta.precio_unitario) - venta.descuento
        if valor_total < 0:
            valor_total = 0

        venta.saldo_pendiente = valor_total - venta.valor_recibido
        if venta.saldo_pendiente < 0:
            venta.saldo_pendiente = 0

        cuenta = request.form.get("cuenta", "").strip()
        if cuenta == "OTRO":
            cuenta = request.form.get("otra_cuenta", "").strip()
            if cuenta == "":
                cuenta = "OTRO"

        venta.cuenta = cuenta
        venta.cliente = request.form.get("cliente", "").strip()
        venta.cliente_cedula = request.form.get("cliente_cedula", "").strip()
        venta.cliente_direccion = request.form.get("cliente_direccion", "").strip()
        venta.cliente_celular = request.form.get("cliente_celular", "").strip()
        venta.cliente_correo = request.form.get("cliente_correo", "").strip()
        venta.observacion = request.form.get("observacion", "").strip()

        sincronizar_movimiento_desde_venta(venta)

        db.session.commit()
        flash("Venta actualizada correctamente.", "success")
        return redirect("/ventas-ecobike")

    return render_template(
        "contabilidad/editar_venta_ecobike.html",
        venta=venta,
        empresa_nombre=empresa_nombre,
        sedes=sedes,
        productos=productos
    )


@ventas_ecobike_bp.route("/ventas-ecobike/eliminar/<int:id>", methods=["POST"])
def eliminar_venta_ecobike(id):
    if "usuario" not in session:
        return redirect("/login")
    if "empresa_id" not in session:
        return redirect("/empresas")
    if not validar_empresa_ecobike():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    venta = VentaEcobike.query.get_or_404(id)

    if venta.empresa_id != empresa_id:
        return redirect("/ventas-ecobike")

    eliminar_movimiento_de_venta(venta.id)
    db.session.delete(venta)
    db.session.commit()
    flash("Venta eliminada correctamente.", "success")
    return redirect("/ventas-ecobike")


@ventas_ecobike_bp.route("/ventas-ecobike/recibo/<int:id>")
def recibo_venta_ecobike(id):
    if "usuario" not in session:
        return redirect("/login")
    if "empresa_id" not in session:
        return redirect("/empresas")
    if not validar_empresa_ecobike():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "ECOBIKE")

    venta = VentaEcobike.query.get_or_404(id)
    if venta.empresa_id != empresa_id:
        return redirect("/ventas-ecobike")

    return render_template(
        "contabilidad/recibo_venta_ecobike.html",
        venta=venta,
        empresa_nombre=empresa_nombre
    )


@ventas_ecobike_bp.route("/ventas-ecobike/reporte")
def reporte_ventas_ecobike():
    if "usuario" not in session:
        return redirect("/login")
    if "empresa_id" not in session:
        return redirect("/empresas")
    if not validar_empresa_ecobike():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "ECOBIKE")

    mes = request.args.get("mes", "").strip()
    sede_id = request.args.get("sede_id", "").strip()
    tipo_venta = request.args.get("tipo_venta", "").strip().upper()

    query = construir_query_ventas_ecobike(
        empresa_id=empresa_id,
        mes=mes,
        sede_id=sede_id,
        tipo_venta=tipo_venta
    )

    ventas = query.order_by(VentaEcobike.fecha.desc(), VentaEcobike.id.desc()).all()
    resumen = construir_resumen_ventas(ventas)

    sedes = Sede.query.filter_by(empresa_id=empresa_id).order_by(Sede.nombre.asc()).all()
    comparativo_sedes = construir_comparativo_sedes(empresa_id, mes)

    labels_sedes = [item["sede"] for item in comparativo_sedes]
    ventas_sedes = [item["valor_total_ventas"] for item in comparativo_sedes]
    recaudo_sedes = [item["recaudo_real"] for item in comparativo_sedes]
    utilidad_sedes = [item["utilidad_bruta"] for item in comparativo_sedes]

    return render_template(
        "contabilidad/reporte_ventas_ecobike.html",
        empresa_nombre=empresa_nombre,
        ventas=ventas,
        sedes=sedes,
        sede_actual=sede_id,
        mes_actual=mes,
        tipo_venta_actual=tipo_venta,
        resumen=resumen,
        comparativo_sedes=comparativo_sedes,
        labels_sedes=labels_sedes,
        ventas_sedes=ventas_sedes,
        recaudo_sedes=recaudo_sedes,
        utilidad_sedes=utilidad_sedes
    )


@ventas_ecobike_bp.route("/ventas-ecobike/exportar-excel")
def exportar_excel_ventas_ecobike():
    if "usuario" not in session:
        return redirect("/login")
    if "empresa_id" not in session:
        return redirect("/empresas")
    if not validar_empresa_ecobike():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")

    mes = request.args.get("mes", "").strip()
    sede_id = request.args.get("sede_id", "").strip()
    tipo_venta = request.args.get("tipo_venta", "").strip().upper()

    query = construir_query_ventas_ecobike(
        empresa_id=empresa_id,
        mes=mes,
        sede_id=sede_id,
        tipo_venta=tipo_venta
    )

    ventas = query.order_by(VentaEcobike.fecha.desc(), VentaEcobike.id.desc()).all()

    data = []
    for v in ventas:
        data.append({
            "Fecha": v.fecha.strftime("%Y-%m-%d"),
            "Sede": v.sede.nombre if v.sede else "General",
            "Referencia": v.referencia,
            "Cantidad": v.cantidad,
            "Precio Unitario": v.precio_unitario,
            "Descuento": v.descuento,
            "Valor Total": v.valor_total,
            "Costo Unitario": v.costo_unitario,
            "Costo Total": v.costo_total,
            "Tipo Venta": v.tipo_venta,
            "Valor Recibido": v.valor_recibido,
            "Saldo Pendiente": v.saldo_pendiente,
            "Cuenta / Medio": v.cuenta if v.cuenta else "",
            "Cliente": v.cliente if v.cliente else "",
            "Cédula": v.cliente_cedula if v.cliente_cedula else "",
            "Dirección": v.cliente_direccion if v.cliente_direccion else "",
            "Celular": v.cliente_celular if v.cliente_celular else "",
            "Correo": v.cliente_correo if v.cliente_correo else "",
            "Observación": v.observacion if v.observacion else ""
        })

    df = pd.DataFrame(data)

    output = BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    output.seek(0)

    return send_file(
        output,
        download_name="ventas_ecobike.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@ventas_ecobike_bp.route("/ventas-ecobike/exportar-pdf")
def exportar_pdf_ventas_ecobike():
    if "usuario" not in session:
        return redirect("/login")
    if "empresa_id" not in session:
        return redirect("/empresas")
    if not validar_empresa_ecobike():
        return redirect("/dashboard")

    from app.pdf_membrete import dibujar_membrete, dibujar_resumen_pdf, COLOR_AZUL, COLOR_BORDE
    empresa_nombre = session.get("empresa_nombre", "ECOBIKE")
    empresa_id = session.get("empresa_id")

    mes = request.args.get("mes", "").strip()
    sede_id = request.args.get("sede_id", "").strip()
    tipo_venta = request.args.get("tipo_venta", "").strip().upper()

    query = construir_query_ventas_ecobike(
        empresa_id=empresa_id,
        mes=mes,
        sede_id=sede_id,
        tipo_venta=tipo_venta
    )

    ventas = query.order_by(VentaEcobike.fecha.desc(), VentaEcobike.id.desc()).all()
    resumen = construir_resumen_ventas(ventas)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)

    y = dibujar_membrete(
        pdf,
        current_app,
        empresa_nombre,
        "Reporte de Ventas",
        "Resumen comercial y recaudo por ventas",
        horizontal=False
    )

    pdf.setFont("Helvetica", 10)
    pdf.setFillColor(colors.black)
    pdf.drawString(40, y, f"Mes: {mes if mes else 'Todos'}")
    pdf.drawString(220, y, f"Tipo: {tipo_venta if tipo_venta else 'Todos'}")

    y -= 18
    dibujar_resumen_pdf(pdf, 40, y, 160, 55, "Recaudo real", f"${resumen['recaudo_real']:,.0f}")
    dibujar_resumen_pdf(pdf, 220, y, 160, 55, "Venta crédito", f"${resumen['valor_credito']:,.0f}")
    dibujar_resumen_pdf(pdf, 400, y, 160, 55, "Ventas totales", f"${resumen['valor_total_ventas']:,.0f}")

    y -= 84

    pdf.setFillColor(COLOR_AZUL)
    pdf.roundRect(40, y - 22, 530, 22, 8, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(48, y - 14, "Fecha")
    pdf.drawString(92, y - 14, "Sede")
    pdf.drawString(145, y - 14, "Referencia")
    pdf.drawString(240, y - 14, "Cant")
    pdf.drawString(275, y - 14, "Tipo")
    pdf.drawString(330, y - 14, "Recibido")
    pdf.drawString(405, y - 14, "Pendiente")
    pdf.drawString(485, y - 14, "Cliente")

    y -= 32
    pdf.setFont("Helvetica", 7)
    pdf.setFillColor(colors.black)

    for v in ventas:
        if y < 55:
            pdf.showPage()
            y = dibujar_membrete(
                pdf,
                current_app,
                empresa_nombre,
                "Reporte de Ventas",
                "Resumen comercial y recaudo por ventas",
                horizontal=False
            )
            pdf.setFillColor(COLOR_AZUL)
            pdf.roundRect(40, y - 22, 530, 22, 8, stroke=0, fill=1)
            pdf.setFillColor(colors.white)
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(48, y - 14, "Fecha")
            pdf.drawString(92, y - 14, "Sede")
            pdf.drawString(145, y - 14, "Referencia")
            pdf.drawString(240, y - 14, "Cant")
            pdf.drawString(275, y - 14, "Tipo")
            pdf.drawString(330, y - 14, "Recibido")
            pdf.drawString(405, y - 14, "Pendiente")
            pdf.drawString(485, y - 14, "Cliente")
            y -= 32
            pdf.setFont("Helvetica", 7)
            pdf.setFillColor(colors.black)

        pdf.drawString(48, y, v.fecha.strftime("%Y-%m-%d"))
        pdf.drawString(92, y, (v.sede.nombre if v.sede else "General")[:10])
        pdf.drawString(145, y, v.referencia[:16])
        pdf.drawString(240, y, str(v.cantidad))
        pdf.drawString(275, y, v.tipo_venta[:8])
        pdf.drawString(330, y, f"${v.valor_recibido:,.0f}")
        pdf.drawString(405, y, f"${v.saldo_pendiente:,.0f}")
        pdf.drawString(485, y, (v.cliente if v.cliente else "")[:15])
        pdf.setStrokeColor(COLOR_BORDE)
        pdf.line(40, y - 4, 570, y - 4)
        y -= 14

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="reporte_ventas_ecobike.pdf",
        mimetype="application/pdf"
    )