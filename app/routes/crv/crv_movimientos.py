"""CRV Movimientos routes."""

from .crv_core import (
    CRVMovimiento,
    CRVTercero,
    Sede,
    _asignar_comprobante_permanente,
    calcular_iva_formulario,
    convertir_fecha,
    convertir_numero,
    crear_o_actualizar_tercero_desde_formulario,
    crv_bp,
    db,
    flash,
    proteger_crv,
    redirect,
    render_template,
    request,
    session,
)

@crv_bp.route("/movimientos")
def movimientos():

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    empresa_nombre = session.get(
        "empresa_nombre",
        "CRV CONSTRUCTORA"
    )

    mes = request.args.get(
        "mes",
        ""
    ).strip()

    sede_id = request.args.get(
        "sede_id",
        ""
    ).strip()

    tipo = request.args.get(
        "tipo",
        ""
    ).strip().upper()

    tercero = request.args.get(
        "tercero",
        ""
    ).strip()

    query = CRVMovimiento.query.filter_by(
        empresa_id=empresa_id
    )

    if sede_id.isdigit():

        query = query.filter_by(
            sede_id=int(sede_id)
        )

    if tipo:

        query = query.filter(
            CRVMovimiento.tipo == tipo
        )

    if tercero:

        query = query.filter(
            CRVMovimiento.tercero_nombre.ilike(
                f"%{tercero}%"
            )
        )

    if mes:

        try:

            anio_texto, mes_texto = mes.split("-")

            query = query.filter(
                db.extract(
                    "year",
                    CRVMovimiento.fecha
                ) == int(anio_texto),

                db.extract(
                    "month",
                    CRVMovimiento.fecha
                ) == int(mes_texto)
            )

        except (ValueError, TypeError):
            pass

    registros = query.order_by(
        CRVMovimiento.fecha.desc(),
        CRVMovimiento.id.desc()
    ).all()

    sedes = Sede.query.filter_by(
        empresa_id=empresa_id
    ).order_by(
        Sede.nombre.asc()
    ).all()

    return render_template(
        "contabilidad/crv_movimientos.html",

        empresa_nombre=empresa_nombre,

        movimientos=registros,

        sedes=sedes,

        mes_actual=mes,
        sede_actual=sede_id,
        tipo_actual=tipo,
        tercero_actual=tercero
    )

@crv_bp.route(
    "/movimientos/nuevo",
    methods=["GET", "POST"]
)
def nuevo_movimiento():

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    empresa_nombre = session.get(
        "empresa_nombre",
        "CRV CONSTRUCTORA"
    )

    sedes = Sede.query.filter_by(
        empresa_id=empresa_id
    ).order_by(
        Sede.nombre.asc()
    ).all()

    terceros = CRVTercero.query.filter_by(
        empresa_id=empresa_id,
        activo=True
    ).order_by(
        CRVTercero.razon_social.asc()
    ).all()

    if request.method == "POST":

        fecha = convertir_fecha(
            request.form.get("fecha")
        )

        if not fecha:

            flash(
                "Debes indicar la fecha contable del movimiento.",
                "error"
            )

            return render_template(
                "contabilidad/crv_nuevo_movimiento.html",
                empresa_nombre=empresa_nombre,
                sedes=sedes,
                terceros=terceros,
                movimiento=None,
                modo="nuevo"
            )

        tipo = request.form.get(
            "tipo",
            ""
        ).strip().upper()

        categoria = request.form.get(
            "categoria",
            ""
        ).strip()

        concepto = request.form.get(
            "concepto",
            ""
        ).strip()

        iva_datos = calcular_iva_formulario(
            request.form
        )

        valor = iva_datos[
            "total_documento"
        ]

        if not tipo:

            flash(
                "Debes seleccionar el tipo de movimiento.",
                "error"
            )

            return redirect(
                "/crv/movimientos/nuevo"
            )

        if not categoria:
            categoria = "OTRO"

        if not concepto:

            flash(
                "Debes escribir el concepto del movimiento.",
                "error"
            )

            return redirect(
                "/crv/movimientos/nuevo"
            )

        tercero_obj = crear_o_actualizar_tercero_desde_formulario(
            empresa_id,
            request.form
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

        descuento = convertir_numero(
            request.form.get("descuento")
        )

        retencion = convertir_numero(
            request.form.get("retencion")
        )

        otros_descuentos = convertir_numero(
            request.form.get(
                "otros_descuentos"
            )
        )

        valor_neto = max(
            0,
            valor
            - descuento
            - retencion
            - otros_descuentos
        )

        movimiento = CRVMovimiento(

            empresa_id=empresa_id,
            sede_id=sede_id,

            fecha=fecha,

            tipo=tipo,

            categoria=categoria,

            subcategoria=request.form.get(
                "subcategoria",
                ""
            ).strip(),

            concepto=concepto,

            descripcion=request.form.get(
                "descripcion",
                ""
            ).strip(),

            tercero_id=(
                tercero_obj.id
                if tercero_obj
                else None
            ),

            tercero_nombre=(
                tercero_obj.razon_social
                if tercero_obj
                else request.form.get(
                    "tercero_nombre",
                    ""
                ).strip()
            ),

            tercero_identificacion=(
                tercero_obj.identificacion
                if tercero_obj
                else request.form.get(
                    "tercero_identificacion",
                    ""
                ).strip()
            ),

            tercero_direccion=(
                tercero_obj.direccion
                if tercero_obj
                else request.form.get(
                    "tercero_direccion",
                    ""
                ).strip()
            ),

            tercero_email=(
                tercero_obj.email
                if tercero_obj
                else request.form.get(
                    "tercero_email",
                    ""
                ).strip()
            ),

            tercero_telefono=(
                (
                    tercero_obj.celular
                    or tercero_obj.telefono
                )
                if tercero_obj
                else request.form.get(
                    "tercero_celular",
                    ""
                ).strip()
            ),

            tercero_contacto=(
                tercero_obj.contacto
                if tercero_obj
                else request.form.get(
                    "tercero_contacto",
                    ""
                ).strip()
            ),

            tipo_documento=request.form.get(
                "tipo_documento",
                ""
            ).strip(),

            numero_documento=request.form.get(
                "numero_documento",
                ""
            ).strip(),

            numero_soporte=request.form.get(
                "numero_soporte",
                ""
            ).strip(),

            fecha_documento=convertir_fecha(
                request.form.get(
                    "fecha_documento"
                )
            ),

            fecha_vencimiento=convertir_fecha(
                request.form.get(
                    "fecha_vencimiento"
                )
            ),

            base_gravable=iva_datos["base_gravable"],
            tipo_iva=iva_datos["tipo_iva"],
            tarifa_iva=iva_datos["tarifa_iva"],
            valor_iva=iva_datos["valor_iva"],
            valor=valor,
            descuento=descuento,
            retencion=retencion,
            otros_descuentos=otros_descuentos,
            valor_neto=valor_neto,

            forma_pago=request.form.get(
                "forma_pago",
                ""
            ).strip(),

            cuenta=request.form.get(
                "cuenta",
                ""
            ).strip(),

            cuenta_destino=request.form.get(
                "cuenta_destino",
                ""
            ).strip(),

            beneficiario=request.form.get(
                "beneficiario",
                ""
            ).strip(),

            referencia_pago=request.form.get(
                "referencia_pago",
                ""
            ).strip(),

            proyecto=request.form.get(
                "proyecto",
                ""
            ).strip(),

            centro_costo=request.form.get(
                "centro_costo",
                ""
            ).strip(),

            obra=request.form.get(
                "obra",
                ""
            ).strip(),

            observaciones=request.form.get(
                "observaciones",
                ""
            ).strip(),

            revisado=False,

            estado="ACTIVO",

            origen_registro="SISTEMA",

            usuario_registro=str(
                session.get(
                    "usuario",
                    ""
                )
            )
        )

        _asignar_comprobante_permanente(
            movimiento
        )

        db.session.add(movimiento)

        db.session.commit()

        flash(
            "Movimiento CRV registrado correctamente.",
            "success"
        )

        return redirect(
            "/crv/movimientos"
        )

    return render_template(
        "contabilidad/crv_nuevo_movimiento.html",

        empresa_nombre=empresa_nombre,

        sedes=sedes,

        terceros=terceros,

        movimiento=None,

        modo="nuevo"
    )

@crv_bp.route(
    "/movimientos/editar/<int:movimiento_id>",
    methods=["GET", "POST"]
)
def editar_movimiento(movimiento_id):

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    empresa_nombre = session.get(
        "empresa_nombre",
        "CRV CONSTRUCTORA"
    )

    movimiento = CRVMovimiento.query.get_or_404(
        movimiento_id
    )

    if movimiento.empresa_id != empresa_id:

        return redirect(
            "/crv/movimientos"
        )

    if movimiento.origen_registro in (
        "CUENTAS_POR_PAGAR",
        "PAGO_CUENTA_POR_PAGAR"
    ):

        flash(
            "Este movimiento fue generado por Cuentas por pagar y debe administrarse desde ese módulo para conservar los saldos correctos.",
            "warning"
        )

        return redirect(
            "/crv/cuentas-por-pagar"
        )

    sedes = Sede.query.filter_by(
        empresa_id=empresa_id
    ).order_by(
        Sede.nombre.asc()
    ).all()

    terceros = CRVTercero.query.filter_by(
        empresa_id=empresa_id,
        activo=True
    ).order_by(
        CRVTercero.razon_social.asc()
    ).all()

    if request.method == "POST":

        fecha = convertir_fecha(
            request.form.get("fecha")
        )

        if not fecha:

            flash(
                "La fecha contable es obligatoria.",
                "error"
            )

            return redirect(
                f"/crv/movimientos/editar/{movimiento_id}"
            )

        tercero_obj = crear_o_actualizar_tercero_desde_formulario(
            empresa_id,
            request.form
        )

        movimiento.fecha = fecha

        movimiento.tipo = request.form.get(
            "tipo",
            ""
        ).strip().upper()

        movimiento.categoria = request.form.get(
            "categoria",
            "OTRO"
        ).strip()

        movimiento.subcategoria = request.form.get(
            "subcategoria",
            ""
        ).strip()

        movimiento.concepto = request.form.get(
            "concepto",
            ""
        ).strip()

        movimiento.descripcion = request.form.get(
            "descripcion",
            ""
        ).strip()

        sede_id_texto = request.form.get(
            "sede_id",
            ""
        ).strip()

        movimiento.sede_id = (
            int(sede_id_texto)
            if sede_id_texto.isdigit()
            else None
        )

        if tercero_obj:

            movimiento.tercero_id = tercero_obj.id

            movimiento.tercero_nombre = tercero_obj.razon_social

            movimiento.tercero_identificacion = tercero_obj.identificacion

            movimiento.tercero_direccion = tercero_obj.direccion

            movimiento.tercero_email = tercero_obj.email

            movimiento.tercero_telefono = (
                tercero_obj.celular
                or tercero_obj.telefono
            )

            movimiento.tercero_contacto = tercero_obj.contacto

        movimiento.tipo_documento = request.form.get(
            "tipo_documento",
            ""
        ).strip()

        movimiento.numero_documento = request.form.get(
            "numero_documento",
            ""
        ).strip()

        movimiento.numero_soporte = request.form.get(
            "numero_soporte",
            ""
        ).strip()

        movimiento.fecha_documento = convertir_fecha(
            request.form.get(
                "fecha_documento"
            )
        )

        movimiento.fecha_vencimiento = convertir_fecha(
            request.form.get(
                "fecha_vencimiento"
            )
        )

        iva_datos = calcular_iva_formulario(
            request.form
        )

        movimiento.base_gravable = iva_datos[
            "base_gravable"
        ]
        movimiento.tipo_iva = iva_datos[
            "tipo_iva"
        ]
        movimiento.tarifa_iva = iva_datos[
            "tarifa_iva"
        ]
        movimiento.valor_iva = iva_datos[
            "valor_iva"
        ]
        movimiento.valor = iva_datos[
            "total_documento"
        ]

        movimiento.descuento = convertir_numero(
            request.form.get("descuento")
        )

        movimiento.retencion = convertir_numero(
            request.form.get("retencion")
        )

        movimiento.otros_descuentos = convertir_numero(
            request.form.get(
                "otros_descuentos"
            )
        )

        movimiento.recalcular_valor_neto()

        movimiento.forma_pago = request.form.get(
            "forma_pago",
            ""
        ).strip()

        movimiento.cuenta = request.form.get(
            "cuenta",
            ""
        ).strip()

        movimiento.cuenta_destino = request.form.get(
            "cuenta_destino",
            ""
        ).strip()

        movimiento.beneficiario = request.form.get(
            "beneficiario",
            ""
        ).strip()

        movimiento.referencia_pago = request.form.get(
            "referencia_pago",
            ""
        ).strip()

        movimiento.proyecto = request.form.get(
            "proyecto",
            ""
        ).strip()

        movimiento.centro_costo = request.form.get(
            "centro_costo",
            ""
        ).strip()

        movimiento.obra = request.form.get(
            "obra",
            ""
        ).strip()

        movimiento.observaciones = request.form.get(
            "observaciones",
            ""
        ).strip()

        db.session.commit()

        flash(
            "Movimiento actualizado correctamente.",
            "success"
        )

        return redirect(
            "/crv/movimientos"
        )

    return render_template(
        "contabilidad/crv_nuevo_movimiento.html",

        empresa_nombre=empresa_nombre,

        sedes=sedes,

        terceros=terceros,

        movimiento=movimiento,

        modo="editar"
    )

@crv_bp.route(
    "/movimientos/eliminar/<int:movimiento_id>",
    methods=["POST"]
)
def eliminar_movimiento(movimiento_id):

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    movimiento = CRVMovimiento.query.get_or_404(
        movimiento_id
    )

    if movimiento.empresa_id != empresa_id:

        return redirect(
            "/crv/movimientos"
        )

    if movimiento.origen_registro in (
        "CUENTAS_POR_PAGAR",
        "PAGO_CUENTA_POR_PAGAR"
    ):

        flash(
            "Este movimiento fue generado por Cuentas por pagar y no debe eliminarse desde Movimientos. Usa el módulo de Cuentas por pagar.",
            "warning"
        )

        return redirect(
            "/crv/cuentas-por-pagar"
        )

    db.session.delete(movimiento)

    db.session.commit()

    flash(
        "Movimiento eliminado correctamente.",
        "success"
    )

    return redirect(
        "/crv/movimientos"
    )

__all__ = ['movimientos', 'nuevo_movimiento', 'editar_movimiento', 'eliminar_movimiento']
