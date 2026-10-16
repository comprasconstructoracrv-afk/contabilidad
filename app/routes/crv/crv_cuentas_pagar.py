"""CRV Cuentas Pagar routes."""

from .crv_core import (
    CRVCuentaPagar,
    CRVMovimiento,
    CRVPagoCuentaPagar,
    CRVTercero,
    Sede,
    _asignar_comprobante_permanente,
    calcular_iva_formulario,
    convertir_fecha,
    convertir_numero,
    crv_bp,
    db,
    flash,
    obtener_movimiento_compra_cxp,
    proteger_crv,
    redirect,
    render_template,
    request,
    session,
    sincronizar_movimiento_compra_cxp,
)

@crv_bp.route(
    "/cuentas-por-pagar",
    methods=["GET", "POST"]
)
def cuentas_por_pagar():

    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "CRV CONSTRUCTORA")

    proveedores = CRVTercero.query.filter(
        CRVTercero.empresa_id == empresa_id,
        CRVTercero.activo.is_(True),
        CRVTercero.tipo_tercero.in_(
            ["PROVEEDOR", "CONTRATISTA", "ENTIDAD", "TERCERO"]
        )
    ).order_by(CRVTercero.razon_social.asc()).all()

    sedes = Sede.query.filter_by(
        empresa_id=empresa_id
    ).order_by(Sede.nombre.asc()).all()

    if request.method == "POST":

        proveedor_id_texto = request.form.get("proveedor_id", "").strip()

        if not proveedor_id_texto.isdigit():
            flash("Debes seleccionar un proveedor válido.", "error")
            return redirect("/crv/cuentas-por-pagar")

        proveedor = CRVTercero.query.get_or_404(int(proveedor_id_texto))

        if proveedor.empresa_id != empresa_id:
            flash("El proveedor seleccionado no pertenece a CRV.", "error")
            return redirect("/crv/cuentas-por-pagar")

        numero_documento = request.form.get("numero_documento", "").strip()
        fecha_documento = convertir_fecha(request.form.get("fecha_documento"))
        concepto = request.form.get("concepto", "").strip()
        iva_datos = calcular_iva_formulario(request.form)
        valor_bruto = iva_datos["total_documento"]

        if not numero_documento:
            flash("El número de documento o factura es obligatorio.", "error")
            return redirect("/crv/cuentas-por-pagar")

        if not fecha_documento:
            flash("La fecha de la factura o documento es obligatoria.", "error")
            return redirect("/crv/cuentas-por-pagar")

        if not concepto:
            flash("El concepto de la obligación es obligatorio.", "error")
            return redirect("/crv/cuentas-por-pagar")

        if valor_bruto <= 0:
            flash("El valor de la factura debe ser mayor a cero.", "error")
            return redirect("/crv/cuentas-por-pagar")

        duplicada = CRVCuentaPagar.query.filter_by(
            empresa_id=empresa_id,
            proveedor_id=proveedor.id,
            numero_documento=numero_documento
        ).first()

        if duplicada:
            flash(
                "Ya existe una cuenta por pagar de este proveedor con el mismo número de documento.",
                "error"
            )
            return redirect(f"/crv/cuentas-por-pagar/{duplicada.id}")

        sede_id_texto = request.form.get("sede_id", "").strip()
        sede_id = int(sede_id_texto) if sede_id_texto.isdigit() else None

        descuento = convertir_numero(request.form.get("descuento"))
        retencion = convertir_numero(request.form.get("retencion"))
        otros_descuentos = convertir_numero(request.form.get("otros_descuentos"))

        cuenta = CRVCuentaPagar(
            empresa_id=empresa_id,
            proveedor_id=proveedor.id,
            sede_id=sede_id,
            tipo_documento=request.form.get("tipo_documento", "").strip(),
            numero_documento=numero_documento,
            fecha_documento=fecha_documento,
            fecha_vencimiento=convertir_fecha(
                request.form.get("fecha_vencimiento")
            ),
            concepto=concepto,
            descripcion=request.form.get("descripcion", "").strip(),
            base_gravable=iva_datos["base_gravable"],
            tipo_iva=iva_datos["tipo_iva"],
            tarifa_iva=iva_datos["tarifa_iva"],
            valor_iva=iva_datos["valor_iva"],
            valor_bruto=valor_bruto,
            descuento=descuento,
            retencion=retencion,
            otros_descuentos=otros_descuentos,
            categoria=request.form.get("categoria", "COMPRA").strip() or "COMPRA",
            subcategoria=request.form.get("subcategoria", "").strip(),
            proyecto=request.form.get("proyecto", "").strip(),
            centro_costo=request.form.get("centro_costo", "").strip(),
            obra=request.form.get("obra", "").strip(),
            observaciones=request.form.get("observaciones", "").strip(),
            origen_registro="CUENTAS_POR_PAGAR",
            usuario_registro=str(session.get("usuario", ""))
        )

        cuenta.valor_neto = cuenta.valor_calculado
        cuenta.total_pagado = 0
        cuenta.saldo_pendiente = cuenta.valor_neto
        cuenta.recalcular_estado()

        try:
            db.session.add(cuenta)
            db.session.flush()

            movimiento_compra = CRVMovimiento(
                empresa_id=empresa_id,
                sede_id=sede_id,
                fecha=fecha_documento,
                tipo="COMPRA",
                categoria=cuenta.categoria or "COMPRA",
                subcategoria=cuenta.subcategoria or "",
                concepto=cuenta.concepto,
                descripcion=cuenta.descripcion or f"Cuenta por pagar {cuenta.numero_documento}",
                tercero_id=proveedor.id,
                tercero_nombre=proveedor.razon_social,
                tercero_identificacion=proveedor.identificacion,
                tercero_direccion=proveedor.direccion or "",
                tercero_email=proveedor.email or "",
                tercero_telefono=proveedor.celular or proveedor.telefono or "",
                tercero_contacto=proveedor.contacto or "",
                tipo_documento=cuenta.tipo_documento or "",
                numero_documento=cuenta.numero_documento,
                numero_soporte=f"CXP-{cuenta.id}",
                fecha_documento=cuenta.fecha_documento,
                fecha_vencimiento=cuenta.fecha_vencimiento,
                base_gravable=cuenta.base_gravable or 0,
                tipo_iva=cuenta.tipo_iva or "NO_APLICA",
                tarifa_iva=cuenta.tarifa_iva or 0,
                valor_iva=cuenta.valor_iva or 0,
                valor=cuenta.valor_bruto or 0,
                descuento=cuenta.descuento or 0,
                retencion=cuenta.retencion or 0,
                otros_descuentos=cuenta.otros_descuentos or 0,
                valor_neto=cuenta.valor_neto or 0,
                forma_pago="CREDITO",
                cuenta="CUENTAS POR PAGAR",
                cuenta_destino="",
                beneficiario=proveedor.razon_social,
                referencia_pago="",
                proyecto=cuenta.proyecto or "",
                centro_costo=cuenta.centro_costo or "",
                obra=cuenta.obra or "",
                observaciones=(
                    "Registro automático generado al crear "
                    f"la cuenta por pagar CXP-{cuenta.id}."
                ),
                revisado=False,
                estado="ACTIVO",
                origen_registro="CUENTAS_POR_PAGAR",
                usuario_registro=str(session.get("usuario", ""))
            )

            _asignar_comprobante_permanente(
                movimiento_compra
            )

            db.session.add(movimiento_compra)
            db.session.commit()

            flash(
                "Cuenta por pagar registrada correctamente. La compra también fue registrada en movimientos.",
                "success"
            )

            return redirect(f"/crv/cuentas-por-pagar/{cuenta.id}")

        except Exception as error:
            db.session.rollback()
            flash(f"No fue posible registrar la cuenta por pagar: {error}", "error")
            return redirect("/crv/cuentas-por-pagar")

    proveedor_id = request.args.get("proveedor_id", "").strip()
    estado = request.args.get("estado", "").strip().upper()
    mes = request.args.get("mes", "").strip()
    buscar = request.args.get("buscar", "").strip()

    query = CRVCuentaPagar.query.filter_by(empresa_id=empresa_id)

    if proveedor_id.isdigit():
        query = query.filter_by(proveedor_id=int(proveedor_id))

    if estado:
        query = query.filter(CRVCuentaPagar.estado == estado)

    if mes:
        try:
            anio_texto, mes_texto = mes.split("-")
            query = query.filter(
                db.extract("year", CRVCuentaPagar.fecha_documento) == int(anio_texto),
                db.extract("month", CRVCuentaPagar.fecha_documento) == int(mes_texto)
            )
        except (ValueError, TypeError):
            pass

    if buscar:
        patron = f"%{buscar}%"
        query = query.join(
            CRVTercero,
            CRVCuentaPagar.proveedor_id == CRVTercero.id
        ).filter(
            db.or_(
                CRVCuentaPagar.numero_documento.ilike(patron),
                CRVCuentaPagar.concepto.ilike(patron),
                CRVTercero.razon_social.ilike(patron),
                CRVTercero.identificacion.ilike(patron)
            )
        )

    registros = query.order_by(
        CRVCuentaPagar.fecha_documento.desc(),
        CRVCuentaPagar.id.desc()
    ).all()

    hubo_cambios = False

    for cuenta in registros:
        estado_anterior = cuenta.estado
        cuenta.recalcular_estado()
        if estado_anterior != cuenta.estado:
            hubo_cambios = True

    if hubo_cambios:
        db.session.commit()

    total_facturado = sum(float(c.valor_neto or 0) for c in registros)
    total_pagado = sum(float(c.total_pagado or 0) for c in registros)
    total_pendiente = sum(float(c.saldo_pendiente or 0) for c in registros)
    total_vencido = sum(
        float(c.saldo_pendiente or 0)
        for c in registros
        if c.estado == "VENCIDA"
    )

    return render_template(
        "contabilidad/crv_cuentas_pagar.html",
        empresa_nombre=empresa_nombre,
        cuentas=registros,
        proveedores=proveedores,
        sedes=sedes,
        proveedor_actual=proveedor_id,
        estado_actual=estado,
        mes_actual=mes,
        buscar_actual=buscar,
        total_facturado=total_facturado,
        total_pagado=total_pagado,
        total_pendiente=total_pendiente,
        total_vencido=total_vencido
    )

@crv_bp.route(
    "/cuentas-por-pagar/<int:cuenta_id>/editar",
    methods=["POST"]
)
def editar_cuenta_por_pagar(cuenta_id):

    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    cuenta = CRVCuentaPagar.query.get_or_404(
        cuenta_id
    )

    if cuenta.empresa_id != empresa_id:

        return redirect(
            "/crv/cuentas-por-pagar"
        )

    proveedor_id_texto = request.form.get(
        "proveedor_id",
        ""
    ).strip()

    if not proveedor_id_texto.isdigit():

        flash(
            "Debes seleccionar un proveedor válido.",
            "error"
        )

        return redirect(
            "/crv/cuentas-por-pagar"
        )

    proveedor = CRVTercero.query.get_or_404(
        int(proveedor_id_texto)
    )

    if proveedor.empresa_id != empresa_id:

        flash(
            "El proveedor seleccionado no pertenece a CRV.",
            "error"
        )

        return redirect(
            "/crv/cuentas-por-pagar"
        )

    numero_documento = request.form.get(
        "numero_documento",
        ""
    ).strip()

    fecha_documento = convertir_fecha(
        request.form.get(
            "fecha_documento"
        )
    )

    fecha_vencimiento = convertir_fecha(
        request.form.get(
            "fecha_vencimiento"
        )
    )

    concepto = request.form.get(
        "concepto",
        ""
    ).strip()

    iva_datos = calcular_iva_formulario(
        request.form
    )

    valor_bruto = iva_datos[
        "total_documento"
    ]

    descuento = convertir_numero(
        request.form.get(
            "descuento"
        )
    )

    retencion = convertir_numero(
        request.form.get(
            "retencion"
        )
    )

    otros_descuentos = convertir_numero(
        request.form.get(
            "otros_descuentos"
        )
    )

    if not numero_documento:

        flash(
            "El número de documento o factura es obligatorio.",
            "error"
        )

        return redirect(
            "/crv/cuentas-por-pagar"
        )

    if not fecha_documento:

        flash(
            "La fecha del documento es obligatoria.",
            "error"
        )

        return redirect(
            "/crv/cuentas-por-pagar"
        )

    if not concepto:

        flash(
            "El concepto de la obligación es obligatorio.",
            "error"
        )

        return redirect(
            "/crv/cuentas-por-pagar"
        )

    if valor_bruto <= 0:

        flash(
            "El valor bruto debe ser mayor a cero.",
            "error"
        )

        return redirect(
            "/crv/cuentas-por-pagar"
        )

    duplicada = CRVCuentaPagar.query.filter(
        CRVCuentaPagar.empresa_id == empresa_id,
        CRVCuentaPagar.proveedor_id == proveedor.id,
        CRVCuentaPagar.numero_documento == numero_documento,
        CRVCuentaPagar.id != cuenta.id
    ).first()

    if duplicada:

        flash(
            "Ya existe otra obligación de este proveedor con el mismo número de documento.",
            "error"
        )

        return redirect(
            "/crv/cuentas-por-pagar"
        )

    nuevo_valor_neto = max(
        0,
        valor_bruto
        - descuento
        - retencion
        - otros_descuentos
    )

    total_pagado = sum(
        float(p.valor_pagado or 0)
        for p in cuenta.pagos
    )

    if nuevo_valor_neto < total_pagado:

        flash(
            "No puedes dejar el valor neto de la obligación por debajo de lo que ya se ha pagado. Primero reversa o corrige los pagos.",
            "error"
        )

        return redirect(
            f"/crv/cuentas-por-pagar/{cuenta.id}"
        )

    sede_id_texto = request.form.get(
        "sede_id",
        ""
    ).strip()

    sede_id = (
        int(sede_id_texto)
        if sede_id_texto.isdigit()
        else None
    )

    try:

        cuenta.proveedor_id = proveedor.id
        cuenta.sede_id = sede_id

        cuenta.tipo_documento = request.form.get(
            "tipo_documento",
            ""
        ).strip()

        cuenta.numero_documento = numero_documento
        cuenta.fecha_documento = fecha_documento
        cuenta.fecha_vencimiento = fecha_vencimiento

        cuenta.concepto = concepto

        cuenta.descripcion = request.form.get(
            "descripcion",
            ""
        ).strip()

        cuenta.base_gravable = iva_datos["base_gravable"]
        cuenta.tipo_iva = iva_datos["tipo_iva"]
        cuenta.tarifa_iva = iva_datos["tarifa_iva"]
        cuenta.valor_iva = iva_datos["valor_iva"]
        cuenta.valor_bruto = valor_bruto
        cuenta.descuento = descuento
        cuenta.retencion = retencion
        cuenta.otros_descuentos = otros_descuentos
        cuenta.valor_neto = nuevo_valor_neto

        cuenta.categoria = request.form.get(
            "categoria",
            "COMPRA"
        ).strip() or "COMPRA"

        cuenta.subcategoria = request.form.get(
            "subcategoria",
            ""
        ).strip()

        cuenta.proyecto = request.form.get(
            "proyecto",
            ""
        ).strip()

        cuenta.centro_costo = request.form.get(
            "centro_costo",
            ""
        ).strip()

        cuenta.obra = request.form.get(
            "obra",
            ""
        ).strip()

        cuenta.observaciones = request.form.get(
            "observaciones",
            ""
        ).strip()

        cuenta.usuario_registro = str(
            session.get(
                "usuario",
                ""
            )
        )

        cuenta.recalcular_saldos()

        sincronizar_movimiento_compra_cxp(
            cuenta
        )

        db.session.commit()

        flash(
            "Cuenta por pagar actualizada correctamente. El movimiento de compra también fue sincronizado.",
            "success"
        )

    except Exception as error:

        db.session.rollback()

        flash(
            f"No fue posible actualizar la cuenta por pagar: {error}",
            "error"
        )

    return redirect(
        f"/crv/cuentas-por-pagar/{cuenta.id}"
    )

@crv_bp.route(
    "/cuentas-por-pagar/<int:cuenta_id>/eliminar",
    methods=["POST"]
)
def eliminar_cuenta_por_pagar(cuenta_id):

    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    cuenta = CRVCuentaPagar.query.get_or_404(
        cuenta_id
    )

    if cuenta.empresa_id != empresa_id:

        return redirect(
            "/crv/cuentas-por-pagar"
        )

    cantidad_pagos = CRVPagoCuentaPagar.query.filter_by(
        empresa_id=empresa_id,
        cuenta_pagar_id=cuenta.id
    ).count()

    if cantidad_pagos > 0:

        flash(
            "No puedes eliminar esta obligación porque tiene pagos registrados. Primero entra al detalle y reversa todos los pagos.",
            "error"
        )

        return redirect(
            f"/crv/cuentas-por-pagar/{cuenta.id}"
        )

    try:

        movimiento_compra = obtener_movimiento_compra_cxp(
            empresa_id,
            cuenta.id
        )

        if movimiento_compra:

            db.session.delete(
                movimiento_compra
            )

        db.session.delete(
            cuenta
        )

        db.session.commit()

        flash(
            "Cuenta por pagar eliminada correctamente. El movimiento de compra asociado también fue eliminado.",
            "success"
        )

    except Exception as error:

        db.session.rollback()

        flash(
            f"No fue posible eliminar la cuenta por pagar: {error}",
            "error"
        )

        return redirect(
            f"/crv/cuentas-por-pagar/{cuenta.id}"
        )

    return redirect(
        "/crv/cuentas-por-pagar"
    )

@crv_bp.route("/cuentas-por-pagar/<int:cuenta_id>")
def cuenta_por_pagar_detalle(cuenta_id):

    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "CRV CONSTRUCTORA")

    cuenta = CRVCuentaPagar.query.get_or_404(cuenta_id)

    if cuenta.empresa_id != empresa_id:
        return redirect("/crv/cuentas-por-pagar")

    cuenta.recalcular_saldos()
    db.session.commit()

    pagos = CRVPagoCuentaPagar.query.filter_by(
        empresa_id=empresa_id,
        cuenta_pagar_id=cuenta.id
    ).order_by(
        CRVPagoCuentaPagar.fecha.desc(),
        CRVPagoCuentaPagar.id.desc()
    ).all()

    return render_template(
        "contabilidad/crv_cuenta_pagar_detalle.html",
        empresa_nombre=empresa_nombre,
        cuenta=cuenta,
        pagos=pagos
    )

@crv_bp.route(
    "/cuentas-por-pagar/<int:cuenta_id>/pagar",
    methods=["POST"]
)
def pagar_cuenta_por_pagar(cuenta_id):

    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    cuenta = CRVCuentaPagar.query.get_or_404(cuenta_id)

    if cuenta.empresa_id != empresa_id:
        return redirect("/crv/cuentas-por-pagar")

    cuenta.recalcular_saldos()

    if cuenta.saldo_pendiente <= 0:
        flash("Esta obligación ya se encuentra pagada.", "warning")
        return redirect(f"/crv/cuentas-por-pagar/{cuenta.id}")

    fecha_pago = convertir_fecha(request.form.get("fecha"))
    valor_pagado = convertir_numero(request.form.get("valor_pagado"))

    if not fecha_pago:
        flash("La fecha real del pago es obligatoria.", "error")
        return redirect(f"/crv/cuentas-por-pagar/{cuenta.id}")

    if valor_pagado <= 0:
        flash("El valor del pago debe ser mayor a cero.", "error")
        return redirect(f"/crv/cuentas-por-pagar/{cuenta.id}")

    if valor_pagado > float(cuenta.saldo_pendiente or 0):
        flash(
            "El pago no puede superar el saldo pendiente de la obligación.",
            "error"
        )
        return redirect(f"/crv/cuentas-por-pagar/{cuenta.id}")

    proveedor = cuenta.proveedor

    pago = CRVPagoCuentaPagar(
        empresa_id=empresa_id,
        cuenta_pagar_id=cuenta.id,
        fecha=fecha_pago,
        valor_pagado=valor_pagado,
        forma_pago=request.form.get("forma_pago", "").strip(),
        cuenta_origen=request.form.get("cuenta_origen", "").strip(),
        cuenta_destino=request.form.get("cuenta_destino", "").strip(),
        beneficiario=request.form.get(
            "beneficiario",
            proveedor.razon_social if proveedor else ""
        ).strip(),
        referencia_pago=request.form.get("referencia_pago", "").strip(),
        numero_soporte=request.form.get("numero_soporte", "").strip(),
        observaciones=request.form.get("observaciones", "").strip(),
        usuario_registro=str(session.get("usuario", ""))
    )

    try:
        db.session.add(pago)
        db.session.flush()

        movimiento_pago = CRVMovimiento(
            empresa_id=empresa_id,
            sede_id=cuenta.sede_id,
            fecha=fecha_pago,
            tipo="PAGO CUENTA POR PAGAR",
            categoria="PAGO PROVEEDOR",
            subcategoria=cuenta.categoria or "",
            concepto=f"Pago cuenta por pagar {cuenta.numero_documento}",
            descripcion=(
                f"Abono/pago a "
                f"{proveedor.razon_social if proveedor else 'proveedor'} "
                f"- documento {cuenta.numero_documento}"
            ),
            tercero_id=proveedor.id if proveedor else None,
            tercero_nombre=proveedor.razon_social if proveedor else "",
            tercero_identificacion=proveedor.identificacion if proveedor else "",
            tercero_direccion=proveedor.direccion if proveedor else "",
            tercero_email=proveedor.email if proveedor else "",
            tercero_telefono=(
                (proveedor.celular or proveedor.telefono or "")
                if proveedor else ""
            ),
            tercero_contacto=proveedor.contacto if proveedor else "",
            tipo_documento="PAGO CXP",
            numero_documento=cuenta.numero_documento,
            numero_soporte=pago.numero_soporte or f"CXP-PAGO-{pago.id}",
            fecha_documento=fecha_pago,
            fecha_vencimiento=None,
            valor=valor_pagado,
            descuento=0,
            retencion=0,
            otros_descuentos=0,
            valor_neto=valor_pagado,
            forma_pago=pago.forma_pago or "",
            cuenta=pago.cuenta_origen or "",
            cuenta_destino=pago.cuenta_destino or "",
            beneficiario=pago.beneficiario or "",
            referencia_pago=pago.referencia_pago or "",
            proyecto=cuenta.proyecto or "",
            centro_costo=cuenta.centro_costo or "",
            obra=cuenta.obra or "",
            observaciones=(
                pago.observaciones
                or f"Movimiento automático generado desde la cuenta por pagar CXP-{cuenta.id}."
            ),
            revisado=False,
            estado="ACTIVO",
            origen_registro="PAGO_CUENTA_POR_PAGAR",
            usuario_registro=str(session.get("usuario", ""))
        )

        _asignar_comprobante_permanente(
            movimiento_pago
        )

        db.session.add(movimiento_pago)
        db.session.flush()

        pago.movimiento_id = movimiento_pago.id

        cuenta.recalcular_saldos()

        db.session.commit()

        flash(
            "Pago registrado correctamente. El saldo fue actualizado y el movimiento quedó registrado.",
            "success"
        )

    except Exception as error:
        db.session.rollback()
        flash(f"No fue posible registrar el pago: {error}", "error")

    return redirect(f"/crv/cuentas-por-pagar/{cuenta.id}")

@crv_bp.route(
    "/cuentas-por-pagar/<int:cuenta_id>/pagos/<int:pago_id>/eliminar",
    methods=["POST"]
)
def eliminar_pago_cuenta_por_pagar(cuenta_id, pago_id):

    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    cuenta = CRVCuentaPagar.query.get_or_404(cuenta_id)

    if cuenta.empresa_id != empresa_id:
        return redirect("/crv/cuentas-por-pagar")

    pago = CRVPagoCuentaPagar.query.get_or_404(pago_id)

    if pago.empresa_id != empresa_id or pago.cuenta_pagar_id != cuenta.id:
        return redirect(f"/crv/cuentas-por-pagar/{cuenta.id}")

    try:
        if pago.movimiento_id:
            movimiento = CRVMovimiento.query.filter_by(
                id=pago.movimiento_id,
                empresa_id=empresa_id
            ).first()

            if movimiento:
                db.session.delete(movimiento)

        db.session.delete(pago)
        db.session.flush()

        cuenta.recalcular_saldos()
        db.session.commit()

        flash(
            "Pago reversado correctamente. El movimiento asociado también fue eliminado.",
            "success"
        )

    except Exception as error:
        db.session.rollback()
        flash(f"No fue posible reversar el pago: {error}", "error")

    return redirect(f"/crv/cuentas-por-pagar/{cuenta.id}")

__all__ = ['cuentas_por_pagar', 'editar_cuenta_por_pagar', 'eliminar_cuenta_por_pagar', 'cuenta_por_pagar_detalle', 'pagar_cuenta_por_pagar', 'eliminar_pago_cuenta_por_pagar']
