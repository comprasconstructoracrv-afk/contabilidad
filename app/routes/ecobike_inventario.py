from datetime import datetime
from flask import Blueprint, render_template, request, redirect, session, flash

from app.extensions import db
from app.models.sede import Sede
from app.models.producto_ecobike import ProductoEcobike
from app.models.inventario_ecobike import InventarioEcobike
from app.models.movimiento_inventario_ecobike import MovimientoInventarioEcobike


ecobike_inventario_bp = Blueprint("ecobike_inventario", __name__)


def validar_empresa_ecobike():
    return session.get("empresa_nombre", "").strip().upper() == "ECOBIKE"


def obtener_o_crear_inventario(empresa_id, producto_id, ubicacion="SEDE", sede_id=None):
    query = InventarioEcobike.query.filter_by(
        empresa_id=empresa_id,
        producto_id=producto_id,
        ubicacion=ubicacion
    )

    if ubicacion == "BODEGA":
        query = query.filter(InventarioEcobike.sede_id.is_(None))
    else:
        query = query.filter_by(sede_id=sede_id)

    inventario = query.first()

    if not inventario:
        inventario = InventarioEcobike(
            empresa_id=empresa_id,
            producto_id=producto_id,
            ubicacion=ubicacion,
            sede_id=None if ubicacion == "BODEGA" else sede_id,
            cantidad=0
        )
        db.session.add(inventario)
        db.session.flush()

    return inventario


def registrar_movimiento_inventario(
    empresa_id,
    producto_id,
    tipo_movimiento,
    cantidad,
    sede_origen_id=None,
    sede_destino_id=None,
    observacion=""
):
    movimiento = MovimientoInventarioEcobike(
        fecha=datetime.utcnow(),
        empresa_id=empresa_id,
        producto_id=producto_id,
        tipo_movimiento=tipo_movimiento,
        cantidad=cantidad,
        sede_origen_id=sede_origen_id,
        sede_destino_id=sede_destino_id,
        observacion=observacion
    )
    db.session.add(movimiento)
    db.session.flush()
    return movimiento


@ecobike_inventario_bp.route("/ecobike/inventario")
def ecobike_inventario():
    if "usuario" not in session:
        return redirect("/login")
    if "empresa_id" not in session:
        return redirect("/empresas")
    if not validar_empresa_ecobike():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "ECOBIKE")

    tipo_producto = request.args.get("tipo_producto", "").strip().upper()
    sede_id = request.args.get("sede_id", "").strip()
    ubicacion = request.args.get("ubicacion", "").strip().upper()

    query = InventarioEcobike.query.join(ProductoEcobike).filter(
        InventarioEcobike.empresa_id == empresa_id
    )

    if tipo_producto in ["BICICLETA", "REPUESTO"]:
        query = query.filter(ProductoEcobike.tipo_producto == tipo_producto)

    if ubicacion in ["BODEGA", "SEDE"]:
        query = query.filter(InventarioEcobike.ubicacion == ubicacion)

    if sede_id.isdigit():
        query = query.filter(InventarioEcobike.sede_id == int(sede_id))

    inventarios = query.order_by(
        ProductoEcobike.tipo_producto.asc(),
        ProductoEcobike.referencia.asc()
    ).all()

    productos = ProductoEcobike.query.filter_by(
        empresa_id=empresa_id,
        activo=True
    ).order_by(
        ProductoEcobike.tipo_producto.asc(),
        ProductoEcobike.referencia.asc()
    ).all()

    sedes = Sede.query.filter_by(empresa_id=empresa_id).order_by(Sede.nombre.asc()).all()

    total_bicicletas = sum(
        int(i.cantidad or 0)
        for i in inventarios
        if i.producto and i.producto.tipo_producto == "BICICLETA"
    )

    total_repuestos = sum(
        int(i.cantidad or 0)
        for i in inventarios
        if i.producto and i.producto.tipo_producto == "REPUESTO"
    )

    stock_bajo = [
        i for i in inventarios
        if i.producto and int(i.cantidad or 0) <= int(i.producto.stock_minimo or 0)
    ]

    return render_template(
        "contabilidad/ecobike_inventario.html",
        empresa_nombre=empresa_nombre,
        inventarios=inventarios,
        productos=productos,
        sedes=sedes,
        tipo_producto_actual=tipo_producto,
        sede_actual=sede_id,
        ubicacion_actual=ubicacion,
        total_bicicletas=total_bicicletas,
        total_repuestos=total_repuestos,
        stock_bajo=stock_bajo
    )


@ecobike_inventario_bp.route("/ecobike/inventario/producto/nuevo", methods=["POST"])
def ecobike_crear_producto():
    if "usuario" not in session:
        return redirect("/login")
    if "empresa_id" not in session:
        return redirect("/empresas")
    if not validar_empresa_ecobike():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")

    tipo_producto = request.form.get("tipo_producto", "BICICLETA").strip().upper()
    if tipo_producto not in ["BICICLETA", "REPUESTO"]:
        tipo_producto = "BICICLETA"

    referencia = request.form.get("referencia", "").strip()
    if not referencia:
        flash("La referencia es obligatoria.", "danger")
        return redirect("/ecobike/inventario")

    producto = ProductoEcobike(
        empresa_id=empresa_id,
        tipo_producto=tipo_producto,
        referencia=referencia,
        marca=request.form.get("marca", "").strip(),
        modelo=request.form.get("modelo", "").strip(),
        color=request.form.get("color", "").strip(),
        talla=request.form.get("talla", "").strip(),
        serial=request.form.get("serial", "").strip(),
        costo_compra=float(request.form.get("costo_compra", "0") or 0),
        precio_venta=float(request.form.get("precio_venta", "0") or 0),
        stock_minimo=int(request.form.get("stock_minimo", "0") or 0),
        activo=True
    )

    db.session.add(producto)
    db.session.commit()

    flash("Producto ECOBIKE creado correctamente.", "success")
    return redirect("/ecobike/inventario")


@ecobike_inventario_bp.route("/ecobike/inventario/entrada", methods=["POST"])
def ecobike_entrada_inventario():
    if "usuario" not in session:
        return redirect("/login")
    if "empresa_id" not in session:
        return redirect("/empresas")
    if not validar_empresa_ecobike():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")

    producto_id = request.form.get("producto_id", "").strip()
    ubicacion = request.form.get("ubicacion", "BODEGA").strip().upper()
    sede_id_texto = request.form.get("sede_id", "").strip()
    cantidad = int(request.form.get("cantidad", "0") or 0)
    observacion = request.form.get("observacion", "").strip()

    if not producto_id.isdigit() or cantidad <= 0:
        flash("Producto y cantidad válida son obligatorios.", "danger")
        return redirect("/ecobike/inventario")

    producto = ProductoEcobike.query.filter_by(
        id=int(producto_id),
        empresa_id=empresa_id
    ).first()

    if not producto:
        flash("Producto no encontrado para ECOBIKE.", "danger")
        return redirect("/ecobike/inventario")

    if ubicacion not in ["BODEGA", "SEDE"]:
        ubicacion = "BODEGA"

    sede_id = None
    if ubicacion == "SEDE":
        if not sede_id_texto.isdigit():
            flash("Debe seleccionar una sede para entrada a sede.", "danger")
            return redirect("/ecobike/inventario")
        sede_id = int(sede_id_texto)

    inventario = obtener_o_crear_inventario(
        empresa_id=empresa_id,
        producto_id=producto.id,
        ubicacion=ubicacion,
        sede_id=sede_id
    )

    inventario.cantidad = int(inventario.cantidad or 0) + cantidad

    registrar_movimiento_inventario(
        empresa_id=empresa_id,
        producto_id=producto.id,
        tipo_movimiento="ENTRADA",
        cantidad=cantidad,
        sede_destino_id=sede_id,
        observacion=observacion or f"Entrada a {ubicacion}"
    )

    db.session.commit()

    flash("Entrada de inventario registrada correctamente.", "success")
    return redirect("/ecobike/inventario")


@ecobike_inventario_bp.route("/ecobike/inventario/traslado", methods=["POST"])
def ecobike_traslado_inventario():
    if "usuario" not in session:
        return redirect("/login")
    if "empresa_id" not in session:
        return redirect("/empresas")
    if not validar_empresa_ecobike():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")

    producto_id = request.form.get("producto_id", "").strip()
    origen_tipo = request.form.get("origen_tipo", "BODEGA").strip().upper()
    destino_tipo = request.form.get("destino_tipo", "SEDE").strip().upper()
    origen_sede_id_texto = request.form.get("origen_sede_id", "").strip()
    destino_sede_id_texto = request.form.get("destino_sede_id", "").strip()
    cantidad = int(request.form.get("cantidad", "0") or 0)
    observacion = request.form.get("observacion", "").strip()

    if not producto_id.isdigit() or cantidad <= 0:
        flash("Producto y cantidad válida son obligatorios.", "danger")
        return redirect("/ecobike/inventario")

    producto = ProductoEcobike.query.filter_by(
        id=int(producto_id),
        empresa_id=empresa_id
    ).first()

    if not producto:
        flash("Producto no encontrado para ECOBIKE.", "danger")
        return redirect("/ecobike/inventario")

    if origen_tipo not in ["BODEGA", "SEDE"]:
        origen_tipo = "BODEGA"

    if destino_tipo not in ["BODEGA", "SEDE"]:
        destino_tipo = "SEDE"

    origen_sede_id = None
    destino_sede_id = None

    if origen_tipo == "SEDE":
        if not origen_sede_id_texto.isdigit():
            flash("Debe seleccionar sede origen.", "danger")
            return redirect("/ecobike/inventario")
        origen_sede_id = int(origen_sede_id_texto)

    if destino_tipo == "SEDE":
        if not destino_sede_id_texto.isdigit():
            flash("Debe seleccionar sede destino.", "danger")
            return redirect("/ecobike/inventario")
        destino_sede_id = int(destino_sede_id_texto)

    if origen_tipo == destino_tipo and origen_sede_id == destino_sede_id:
        flash("El origen y destino no pueden ser iguales.", "danger")
        return redirect("/ecobike/inventario")

    inventario_origen = obtener_o_crear_inventario(
        empresa_id=empresa_id,
        producto_id=producto.id,
        ubicacion=origen_tipo,
        sede_id=origen_sede_id
    )

    if int(inventario_origen.cantidad or 0) < cantidad:
        flash("No hay inventario suficiente en el origen.", "danger")
        return redirect("/ecobike/inventario")

    inventario_destino = obtener_o_crear_inventario(
        empresa_id=empresa_id,
        producto_id=producto.id,
        ubicacion=destino_tipo,
        sede_id=destino_sede_id
    )

    inventario_origen.cantidad = int(inventario_origen.cantidad or 0) - cantidad
    inventario_destino.cantidad = int(inventario_destino.cantidad or 0) + cantidad

    registrar_movimiento_inventario(
        empresa_id=empresa_id,
        producto_id=producto.id,
        tipo_movimiento="TRASLADO",
        cantidad=cantidad,
        sede_origen_id=origen_sede_id,
        sede_destino_id=destino_sede_id,
        observacion=observacion or f"Traslado {origen_tipo} a {destino_tipo}"
    )

    db.session.commit()

    flash("Traslado de inventario registrado correctamente.", "success")
    return redirect("/ecobike/inventario")


@ecobike_inventario_bp.route("/ecobike/inventario/ajuste", methods=["POST"])
def ecobike_ajuste_inventario():
    if "usuario" not in session:
        return redirect("/login")
    if "empresa_id" not in session:
        return redirect("/empresas")
    if not validar_empresa_ecobike():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")

    producto_id = request.form.get("producto_id", "").strip()
    ubicacion = request.form.get("ubicacion", "BODEGA").strip().upper()
    sede_id_texto = request.form.get("sede_id", "").strip()
    nueva_cantidad = int(request.form.get("nueva_cantidad", "0") or 0)
    observacion = request.form.get("observacion", "").strip()

    if not producto_id.isdigit() or nueva_cantidad < 0:
        flash("Producto y cantidad válida son obligatorios.", "danger")
        return redirect("/ecobike/inventario")

    producto = ProductoEcobike.query.filter_by(
        id=int(producto_id),
        empresa_id=empresa_id
    ).first()

    if not producto:
        flash("Producto no encontrado para ECOBIKE.", "danger")
        return redirect("/ecobike/inventario")

    if ubicacion not in ["BODEGA", "SEDE"]:
        ubicacion = "BODEGA"

    sede_id = None
    if ubicacion == "SEDE":
        if not sede_id_texto.isdigit():
            flash("Debe seleccionar una sede para ajustar inventario de sede.", "danger")
            return redirect("/ecobike/inventario")
        sede_id = int(sede_id_texto)

    inventario = obtener_o_crear_inventario(
        empresa_id=empresa_id,
        producto_id=producto.id,
        ubicacion=ubicacion,
        sede_id=sede_id
    )

    cantidad_anterior = int(inventario.cantidad or 0)
    diferencia = nueva_cantidad - cantidad_anterior

    inventario.cantidad = nueva_cantidad

    registrar_movimiento_inventario(
        empresa_id=empresa_id,
        producto_id=producto.id,
        tipo_movimiento="AJUSTE",
        cantidad=diferencia,
        sede_destino_id=sede_id,
        observacion=observacion or f"Ajuste de {cantidad_anterior} a {nueva_cantidad}"
    )

    db.session.commit()

    flash("Ajuste de inventario registrado correctamente.", "success")
    return redirect("/ecobike/inventario")


@ecobike_inventario_bp.route("/ecobike/inventario/movimientos")
def ecobike_movimientos_inventario():
    if "usuario" not in session:
        return redirect("/login")
    if "empresa_id" not in session:
        return redirect("/empresas")
    if not validar_empresa_ecobike():
        return redirect("/dashboard")

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "ECOBIKE")

    movimientos = MovimientoInventarioEcobike.query.filter_by(
        empresa_id=empresa_id
    ).order_by(
        MovimientoInventarioEcobike.fecha.desc(),
        MovimientoInventarioEcobike.id.desc()
    ).all()

    return render_template(
        "contabilidad/ecobike_movimientos_inventario.html",
        empresa_nombre=empresa_nombre,
        movimientos=movimientos
    )