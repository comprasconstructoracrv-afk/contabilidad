"""CRV Cuentas Cobrar routes."""

from .crv_core import (
    CRVCobroCuentaCobrar,
    CRVCuentaCobrar,
    CRVMovimiento,
    CRVTercero,
    Sede,
    _asignar_comprobante_permanente,
    _clientes_crv,
    _cuentas_financieras_crv,
    _sincronizar_movimiento_cxc,
    calcular_iva_formulario,
    convertir_fecha,
    convertir_numero,
    crv_bp,
    db,
    flash,
    proteger_crv,
    redirect,
    render_template,
    request,
    session,
)

@crv_bp.route("/cuentas-por-cobrar", methods=["GET", "POST"])
def cuentas_por_cobrar():
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "CRV CONSTRUCTORA")

    if request.method == "POST":
        cliente_id = request.form.get("cliente_id", "").strip()
        numero_documento = request.form.get("numero_documento", "").strip()
        fecha_documento = convertir_fecha(request.form.get("fecha_documento"))

        if not cliente_id.isdigit() or not numero_documento or not fecha_documento:
            flash("Cliente, documento y fecha son obligatorios.", "error")
            return redirect("/crv/cuentas-por-cobrar")

        cliente = CRVTercero.query.filter_by(
            id=int(cliente_id),
            empresa_id=empresa_id
        ).first()

        if cliente is None:
            flash("El cliente seleccionado no pertenece a CRV.", "error")
            return redirect("/crv/cuentas-por-cobrar")

        existe = CRVCuentaCobrar.query.filter_by(
            empresa_id=empresa_id,
            numero_documento=numero_documento
        ).first()

        if existe:
            flash("Ya existe una cuenta por cobrar con ese documento.", "error")
            return redirect("/crv/cuentas-por-cobrar")

        sede_texto = request.form.get("sede_id", "").strip()
        sede_id = int(sede_texto) if sede_texto.isdigit() else None

        iva_datos = calcular_iva_formulario(
            request.form
        )

        cuenta = CRVCuentaCobrar(
            empresa_id=empresa_id,
            cliente_id=cliente.id,
            sede_id=sede_id,
            tipo_documento=request.form.get("tipo_documento", "FACTURA").strip(),
            numero_documento=numero_documento,
            fecha_documento=fecha_documento,
            fecha_vencimiento=convertir_fecha(request.form.get("fecha_vencimiento")),
            concepto=request.form.get("concepto", "").strip() or "Cuenta por cobrar",
            descripcion=request.form.get("descripcion", "").strip(),
            base_gravable=iva_datos["base_gravable"],
            tipo_iva=iva_datos["tipo_iva"],
            tarifa_iva=iva_datos["tarifa_iva"],
            valor_iva=iva_datos["valor_iva"],
            valor_bruto=iva_datos["total_documento"],
            descuento=convertir_numero(request.form.get("descuento")),
            retencion=convertir_numero(request.form.get("retencion")),
            otros_descuentos=convertir_numero(request.form.get("otros_descuentos")),
            categoria=request.form.get("categoria", "VENTA / CUENTA POR COBRAR").strip(),
            subcategoria=request.form.get("subcategoria", "").strip(),
            proyecto=request.form.get("proyecto", "").strip(),
            centro_costo=request.form.get("centro_costo", "").strip(),
            obra=request.form.get("obra", "").strip(),
            observaciones=request.form.get("observaciones", "").strip(),
            origen_registro="SISTEMA",
            usuario_registro=str(session.get("usuario", ""))
        )

        if cuenta.valor_bruto <= 0:
            flash("El valor bruto debe ser mayor a cero.", "error")
            return redirect("/crv/cuentas-por-cobrar")

        try:
            db.session.add(cuenta)
            db.session.flush()
            cuenta.recalcular_saldos()
            _sincronizar_movimiento_cxc(cuenta)
            db.session.commit()
            flash("Cuenta por cobrar registrada correctamente.", "success")
            return redirect(f"/crv/cuentas-por-cobrar/{cuenta.id}")
        except Exception as error:
            db.session.rollback()
            flash(f"No fue posible guardar la cuenta por cobrar: {error}", "error")
            return redirect("/crv/cuentas-por-cobrar")

    mes = request.args.get("mes", "").strip()
    cliente_filtro = request.args.get("cliente_id", "").strip()
    estado = request.args.get("estado", "").strip().upper()
    buscar = request.args.get("buscar", "").strip()

    query = CRVCuentaCobrar.query.filter_by(empresa_id=empresa_id)

    if mes:
        try:
            anio, numero_mes = mes.split("-")
            query = query.filter(
                db.extract("year", CRVCuentaCobrar.fecha_documento) == int(anio),
                db.extract("month", CRVCuentaCobrar.fecha_documento) == int(numero_mes)
            )
        except ValueError:
            pass

    if cliente_filtro.isdigit():
        query = query.filter_by(cliente_id=int(cliente_filtro))

    cuentas = query.order_by(
        CRVCuentaCobrar.fecha_documento.desc(),
        CRVCuentaCobrar.id.desc()
    ).all()

    for cuenta in cuentas:
        cuenta.recalcular_saldos()

    if estado:
        cuentas = [c for c in cuentas if c.estado == estado]

    if buscar:
        buscar_low = buscar.lower()
        cuentas = [
            c for c in cuentas
            if buscar_low in (c.numero_documento or "").lower()
            or buscar_low in (c.concepto or "").lower()
            or buscar_low in ((c.cliente.razon_social if c.cliente else "").lower())
            or buscar_low in ((c.cliente.identificacion if c.cliente else "").lower())
        ]

    total_facturado = sum(float(c.valor_neto or 0) for c in cuentas)
    total_cobrado = sum(float(c.total_cobrado or 0) for c in cuentas)
    total_pendiente = sum(float(c.saldo_pendiente or 0) for c in cuentas)
    total_vencido = sum(
        float(c.saldo_pendiente or 0)
        for c in cuentas
        if c.estado == "VENCIDA"
    )

    db.session.commit()

    return render_template(
        "contabilidad/crv_cuentas_cobrar.html",
        empresa_nombre=empresa_nombre,
        cuentas=cuentas,
        clientes=_clientes_crv(empresa_id),
        sedes=Sede.query.filter_by(empresa_id=empresa_id).order_by(Sede.nombre.asc()).all(),
        mes_actual=mes,
        cliente_actual=cliente_filtro,
        estado_actual=estado,
        buscar_actual=buscar,
        total_facturado=total_facturado,
        total_cobrado=total_cobrado,
        total_pendiente=total_pendiente,
        total_vencido=total_vencido
    )

@crv_bp.route("/cuentas-por-cobrar/<int:cuenta_id>")
def cuenta_cobrar_detalle(cuenta_id):
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    cuenta = CRVCuentaCobrar.query.get_or_404(cuenta_id)

    if cuenta.empresa_id != empresa_id:
        return redirect("/crv/cuentas-por-cobrar")

    cuenta.recalcular_saldos()
    db.session.commit()

    return render_template(
        "contabilidad/crv_cuenta_cobrar_detalle.html",
        empresa_nombre=session.get("empresa_nombre", "CRV CONSTRUCTORA"),
        cuenta=cuenta,
        cobros=sorted(cuenta.cobros, key=lambda x: (x.fecha, x.id), reverse=True),
        cuentas_financieras=_cuentas_financieras_crv(empresa_id)
    )

@crv_bp.route("/cuentas-por-cobrar/<int:cuenta_id>/editar", methods=["POST"])
def cuenta_cobrar_editar(cuenta_id):
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    cuenta = CRVCuentaCobrar.query.get_or_404(cuenta_id)

    if cuenta.empresa_id != empresa_id:
        return redirect("/crv/cuentas-por-cobrar")

    cliente_id = request.form.get("cliente_id", "").strip()
    cliente = CRVTercero.query.filter_by(
        id=int(cliente_id) if cliente_id.isdigit() else -1,
        empresa_id=empresa_id
    ).first()

    if cliente is None:
        flash("Cliente inválido.", "error")
        return redirect("/crv/cuentas-por-cobrar")

    iva_datos = calcular_iva_formulario(request.form)
    nuevo_bruto = iva_datos["total_documento"]
    descuento = convertir_numero(request.form.get("descuento"))
    retencion = convertir_numero(request.form.get("retencion"))
    otros = convertir_numero(request.form.get("otros_descuentos"))
    nuevo_neto = max(0, nuevo_bruto - descuento - retencion - otros)

    if nuevo_neto < float(cuenta.total_cobrado or 0):
        flash("No puedes dejar el valor neto por debajo de lo ya cobrado.", "error")
        return redirect("/crv/cuentas-por-cobrar")

    sede_texto = request.form.get("sede_id", "").strip()

    cuenta.cliente_id = cliente.id
    cuenta.sede_id = int(sede_texto) if sede_texto.isdigit() else None
    cuenta.tipo_documento = request.form.get("tipo_documento", "").strip()
    cuenta.numero_documento = request.form.get("numero_documento", "").strip()
    cuenta.fecha_documento = convertir_fecha(request.form.get("fecha_documento")) or cuenta.fecha_documento
    cuenta.fecha_vencimiento = convertir_fecha(request.form.get("fecha_vencimiento"))
    cuenta.concepto = request.form.get("concepto", "").strip()
    cuenta.descripcion = request.form.get("descripcion", "").strip()
    cuenta.base_gravable = iva_datos["base_gravable"]
    cuenta.tipo_iva = iva_datos["tipo_iva"]
    cuenta.tarifa_iva = iva_datos["tarifa_iva"]
    cuenta.valor_iva = iva_datos["valor_iva"]
    cuenta.valor_bruto = nuevo_bruto
    cuenta.descuento = descuento
    cuenta.retencion = retencion
    cuenta.otros_descuentos = otros
    cuenta.categoria = request.form.get("categoria", "").strip()
    cuenta.subcategoria = request.form.get("subcategoria", "").strip()
    cuenta.proyecto = request.form.get("proyecto", "").strip()
    cuenta.centro_costo = request.form.get("centro_costo", "").strip()
    cuenta.obra = request.form.get("obra", "").strip()
    cuenta.observaciones = request.form.get("observaciones", "").strip()
    cuenta.recalcular_saldos()
    _sincronizar_movimiento_cxc(cuenta)

    try:
        db.session.commit()
        flash("Cuenta por cobrar actualizada correctamente.", "success")
    except Exception as error:
        db.session.rollback()
        flash(f"No fue posible actualizar: {error}", "error")

    return redirect("/crv/cuentas-por-cobrar")

@crv_bp.route("/cuentas-por-cobrar/<int:cuenta_id>/eliminar", methods=["POST"])
def cuenta_cobrar_eliminar(cuenta_id):
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    cuenta = CRVCuentaCobrar.query.get_or_404(cuenta_id)

    if cuenta.empresa_id != empresa_id:
        return redirect("/crv/cuentas-por-cobrar")

    if cuenta.cobros:
        flash("No se puede eliminar una cuenta con cobros. Primero revierte los cobros.", "warning")
        return redirect("/crv/cuentas-por-cobrar")

    movimiento = CRVMovimiento.query.filter_by(
        empresa_id=empresa_id,
        origen_registro=f"CUENTA_POR_COBRAR:{cuenta.id}"
    ).first()

    try:
        if movimiento:
            db.session.delete(movimiento)
        db.session.delete(cuenta)
        db.session.commit()
        flash("Cuenta por cobrar eliminada correctamente.", "success")
    except Exception as error:
        db.session.rollback()
        flash(f"No fue posible eliminar la cuenta: {error}", "error")

    return redirect("/crv/cuentas-por-cobrar")

@crv_bp.route("/cuentas-por-cobrar/<int:cuenta_id>/cobrar", methods=["POST"])
def cuenta_cobrar_registrar_cobro(cuenta_id):
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    cuenta = CRVCuentaCobrar.query.get_or_404(cuenta_id)

    if cuenta.empresa_id != empresa_id:
        return redirect("/crv/cuentas-por-cobrar")

    cuenta.recalcular_saldos()

    fecha = convertir_fecha(request.form.get("fecha"))
    valor = convertir_numero(request.form.get("valor_cobrado"))
    cuenta_receptora = request.form.get("cuenta_receptora", "").strip()

    if not fecha or valor <= 0:
        flash("Fecha y valor del cobro son obligatorios.", "error")
        return redirect(f"/crv/cuentas-por-cobrar/{cuenta.id}")

    if valor > float(cuenta.saldo_pendiente or 0):
        flash("El cobro no puede superar el saldo pendiente.", "error")
        return redirect(f"/crv/cuentas-por-cobrar/{cuenta.id}")

    if not cuenta_receptora:
        flash("Selecciona la cuenta propia de CRV que recibió el dinero.", "error")
        return redirect(f"/crv/cuentas-por-cobrar/{cuenta.id}")

    cliente = cuenta.cliente

    cobro = CRVCobroCuentaCobrar(
        empresa_id=empresa_id,
        cuenta_cobrar_id=cuenta.id,
        fecha=fecha,
        valor_cobrado=valor,
        forma_pago=request.form.get("forma_pago", "").strip(),
        cuenta_receptora=cuenta_receptora,
        cuenta_origen_cliente=request.form.get("cuenta_origen_cliente", "").strip(),
        pagador=request.form.get("pagador", "").strip() or (cliente.razon_social if cliente else ""),
        referencia_pago=request.form.get("referencia_pago", "").strip(),
        numero_soporte=request.form.get("numero_soporte", "").strip(),
        observaciones=request.form.get("observaciones", "").strip(),
        usuario_registro=str(session.get("usuario", ""))
    )

    try:
        db.session.add(cobro)
        db.session.flush()

        movimiento = CRVMovimiento(
            empresa_id=empresa_id,
            sede_id=cuenta.sede_id,
            fecha=fecha,
            tipo="COBRO CUENTA POR COBRAR",
            categoria="COBRO CLIENTE",
            subcategoria=cuenta.categoria or "",
            concepto=f"Cobro cuenta por cobrar {cuenta.numero_documento}",
            descripcion=f"Cobro recibido de {cliente.razon_social if cliente else 'cliente'} - documento {cuenta.numero_documento}",
            tercero_id=cliente.id if cliente else None,
            tercero_nombre=cliente.razon_social if cliente else "",
            tercero_identificacion=cliente.identificacion if cliente else "",
            tercero_direccion=cliente.direccion if cliente else "",
            tercero_email=cliente.email if cliente else "",
            tercero_telefono=((cliente.celular or cliente.telefono or "") if cliente else ""),
            tercero_contacto=cliente.contacto if cliente else "",
            tipo_documento="COBRO CXC",
            numero_documento=cuenta.numero_documento,
            numero_soporte=cobro.numero_soporte or f"CXC-COBRO-{cobro.id}",
            fecha_documento=fecha,
            fecha_vencimiento=None,
            valor=valor,
            descuento=0,
            retencion=0,
            otros_descuentos=0,
            valor_neto=valor,
            forma_pago=cobro.forma_pago or "",
            cuenta=cuenta_receptora,
            cuenta_destino="",
            beneficiario="CRV CONSTRUCTORA",
            referencia_pago=cobro.referencia_pago or "",
            proyecto=cuenta.proyecto or "",
            centro_costo=cuenta.centro_costo or "",
            obra=cuenta.obra or "",
            observaciones=cobro.observaciones or "Cobro automático generado desde cuentas por cobrar.",
            revisado=False,
            estado="ACTIVO",
            origen_registro="COBRO_CUENTA_POR_COBRAR",
            usuario_registro=str(session.get("usuario", ""))
        )

        _asignar_comprobante_permanente(
            movimiento
        )

        db.session.add(movimiento)
        db.session.flush()
        cobro.movimiento_id = movimiento.id
        cuenta.recalcular_saldos()
        db.session.commit()
        flash("Cobro registrado correctamente.", "success")
    except Exception as error:
        db.session.rollback()
        flash(f"No fue posible registrar el cobro: {error}", "error")

    return redirect(f"/crv/cuentas-por-cobrar/{cuenta.id}")

@crv_bp.route("/cuentas-por-cobrar/<int:cuenta_id>/cobros/<int:cobro_id>/eliminar", methods=["POST"])
def cuenta_cobrar_reversar_cobro(cuenta_id, cobro_id):
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    cuenta = CRVCuentaCobrar.query.get_or_404(cuenta_id)
    cobro = CRVCobroCuentaCobrar.query.get_or_404(cobro_id)

    if cuenta.empresa_id != empresa_id or cobro.empresa_id != empresa_id or cobro.cuenta_cobrar_id != cuenta.id:
        return redirect("/crv/cuentas-por-cobrar")

    try:
        if cobro.movimiento:
            db.session.delete(cobro.movimiento)
        db.session.delete(cobro)
        db.session.flush()
        cuenta.recalcular_saldos()
        db.session.commit()
        flash("Cobro reversado correctamente.", "success")
    except Exception as error:
        db.session.rollback()
        flash(f"No fue posible reversar el cobro: {error}", "error")

    return redirect(f"/crv/cuentas-por-cobrar/{cuenta.id}")

__all__ = ['cuentas_por_cobrar', 'cuenta_cobrar_detalle', 'cuenta_cobrar_editar', 'cuenta_cobrar_eliminar', 'cuenta_cobrar_registrar_cobro', 'cuenta_cobrar_reversar_cobro']
