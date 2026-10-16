"""CRV Bancos routes."""

from .crv_core import (
    CRVMovimiento,
    _asignar_comprobante_permanente,
    _cuentas_financieras_crv,
    _movimiento_es_bancario,
    _nombre_cuenta_valido,
    _valor_movimiento_bancario,
    convertir_fecha,
    convertir_numero,
    crv_bp,
    datetime,
    db,
    flash,
    proteger_crv,
    redirect,
    render_template,
    request,
    session,
)

@crv_bp.route(
    "/bancos-caja",
    methods=["GET", "POST"]
)
def bancos_caja():

    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get(
        "empresa_nombre",
        "CRV CONSTRUCTORA"
    )

    if request.method == "POST":

        accion = request.form.get(
            "accion",
            ""
        ).strip().lower()

        # ----------------------------------------------------
        # CREAR CUENTA / SALDO INICIAL
        # ----------------------------------------------------

        if accion == "crear_cuenta":

            nombre = request.form.get(
                "nombre_cuenta",
                ""
            ).strip()

            tipo_cuenta = request.form.get(
                "tipo_cuenta",
                "BANCO"
            ).strip().upper()

            fecha = convertir_fecha(
                request.form.get("fecha_apertura")
            )

            saldo_inicial = convertir_numero(
                request.form.get("saldo_inicial")
            )

            observaciones = request.form.get(
                "observaciones",
                ""
            ).strip()

            if not nombre:
                flash(
                    "Debes escribir el nombre de la cuenta.",
                    "error"
                )
                return redirect("/crv/bancos-caja")

            if not fecha:
                flash(
                    "Debes indicar la fecha del saldo inicial.",
                    "error"
                )
                return redirect("/crv/bancos-caja")

            cuentas_existentes = {
                fila["nombre"].strip().upper()
                for fila in _cuentas_financieras_crv(empresa_id)
            }

            if nombre.strip().upper() in cuentas_existentes:
                flash(
                    "Ya existe una cuenta financiera con ese nombre.",
                    "error"
                )
                return redirect("/crv/bancos-caja")

            registro = CRVMovimiento(
                empresa_id=empresa_id,
                sede_id=None,
                fecha=fecha,
                tipo="SALDO INICIAL CUENTA",
                categoria="BANCOS Y CAJA",
                subcategoria=tipo_cuenta,
                concepto=f"Saldo inicial - {nombre}",
                descripcion=(
                    f"Apertura/control de cuenta financiera {nombre}"
                ),
                tercero_id=None,
                tercero_nombre="",
                tercero_identificacion="",
                tercero_direccion="",
                tercero_email="",
                tercero_telefono="",
                tercero_contacto="",
                tipo_documento="SALDO INICIAL",
                numero_documento="",
                numero_soporte=(
                    f"BC-INICIAL-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                ),
                fecha_documento=fecha,
                fecha_vencimiento=None,
                valor=saldo_inicial,
                descuento=0,
                retencion=0,
                otros_descuentos=0,
                valor_neto=saldo_inicial,
                forma_pago=tipo_cuenta,
                cuenta=nombre,
                cuenta_destino="",
                beneficiario="CRV CONSTRUCTORA",
                referencia_pago="",
                proyecto="",
                centro_costo="",
                obra="",
                observaciones=observaciones,
                revisado=False,
                estado="ACTIVO",
                origen_registro="BANCOS_CAJA_SALDO_INICIAL",
                usuario_registro=str(session.get("usuario", ""))
            )

            try:
                _asignar_comprobante_permanente(
                    registro
                )

                db.session.add(registro)
                db.session.commit()

                flash(
                    "Cuenta financiera creada correctamente.",
                    "success"
                )

            except Exception as error:
                db.session.rollback()
                flash(
                    f"No fue posible crear la cuenta: {error}",
                    "error"
                )

            return redirect("/crv/bancos-caja")

        # ----------------------------------------------------
        # TRANSFERENCIA ENTRE CUENTAS
        # ----------------------------------------------------

        if accion == "transferencia":

            fecha = convertir_fecha(
                request.form.get("fecha")
            )

            cuenta_origen = request.form.get(
                "cuenta_origen",
                ""
            ).strip()

            cuenta_destino = request.form.get(
                "cuenta_destino",
                ""
            ).strip()

            valor = convertir_numero(
                request.form.get("valor")
            )

            referencia = request.form.get(
                "referencia_pago",
                ""
            ).strip()

            observaciones = request.form.get(
                "observaciones",
                ""
            ).strip()

            if not fecha:
                flash(
                    "La fecha real de la transferencia es obligatoria.",
                    "error"
                )
                return redirect("/crv/bancos-caja")

            if not cuenta_origen or not cuenta_destino:
                flash(
                    "Debes seleccionar cuenta de origen y destino.",
                    "error"
                )
                return redirect("/crv/bancos-caja")

            if cuenta_origen == cuenta_destino:
                flash(
                    "La cuenta de origen y destino deben ser diferentes.",
                    "error"
                )
                return redirect("/crv/bancos-caja")

            if valor <= 0:
                flash(
                    "El valor de la transferencia debe ser mayor a cero.",
                    "error"
                )
                return redirect("/crv/bancos-caja")

            cuentas_actuales = {
                fila["nombre"]: fila
                for fila in _cuentas_financieras_crv(empresa_id)
            }

            if (
                cuenta_origen not in cuentas_actuales
                or cuenta_destino not in cuentas_actuales
            ):
                flash(
                    "Una de las cuentas seleccionadas no existe.",
                    "error"
                )
                return redirect("/crv/bancos-caja")

            saldo_origen = float(
                cuentas_actuales[cuenta_origen]["saldo"] or 0
            )

            if valor > saldo_origen:
                flash(
                    "La transferencia supera el saldo calculado de la cuenta de origen.",
                    "error"
                )
                return redirect("/crv/bancos-caja")

            movimiento = CRVMovimiento(
                empresa_id=empresa_id,
                sede_id=None,
                fecha=fecha,
                tipo="TRANSFERENCIA",
                categoria="BANCOS Y CAJA",
                subcategoria="TRANSFERENCIA INTERNA",
                concepto=(
                    f"Transferencia {cuenta_origen} → {cuenta_destino}"
                ),
                descripcion=(
                    f"Transferencia entre cuentas propias de CRV: "
                    f"{cuenta_origen} a {cuenta_destino}"
                ),
                tercero_id=None,
                tercero_nombre="CRV CONSTRUCTORA",
                tercero_identificacion="",
                tercero_direccion="",
                tercero_email="",
                tercero_telefono="",
                tercero_contacto="",
                tipo_documento="TRANSFERENCIA INTERNA",
                numero_documento="",
                numero_soporte=(
                    f"BC-TRF-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                ),
                fecha_documento=fecha,
                fecha_vencimiento=None,
                valor=valor,
                descuento=0,
                retencion=0,
                otros_descuentos=0,
                valor_neto=valor,
                forma_pago="TRANSFERENCIA",
                cuenta=cuenta_origen,
                cuenta_destino=cuenta_destino,
                beneficiario="CRV CONSTRUCTORA",
                referencia_pago=referencia,
                proyecto="",
                centro_costo="",
                obra="",
                observaciones=observaciones,
                revisado=False,
                estado="ACTIVO",
                origen_registro="BANCOS_CAJA_TRANSFERENCIA",
                usuario_registro=str(session.get("usuario", ""))
            )

            try:
                _asignar_comprobante_permanente(
                    movimiento
                )

                db.session.add(movimiento)
                db.session.commit()

                flash(
                    "Transferencia registrada correctamente. No afecta el resultado financiero.",
                    "success"
                )

            except Exception as error:
                db.session.rollback()
                flash(
                    f"No fue posible registrar la transferencia: {error}",
                    "error"
                )

            return redirect("/crv/bancos-caja")

    # --------------------------------------------------------
    # CONSULTA
    # --------------------------------------------------------

    mes = request.args.get(
        "mes",
        ""
    ).strip()

    cuenta_filtro = request.args.get(
        "cuenta",
        ""
    ).strip()

    cuentas = _cuentas_financieras_crv(
        empresa_id
    )

    movimientos_query = CRVMovimiento.query.filter_by(
        empresa_id=empresa_id
    )

    movimientos = movimientos_query.order_by(
        CRVMovimiento.fecha.desc(),
        CRVMovimiento.id.desc()
    ).all()

    movimientos_bancarios = [
        m
        for m in movimientos
        if _movimiento_es_bancario(m)
    ]

    if mes:
        try:
            anio_texto, mes_texto = mes.split("-")
            anio = int(anio_texto)
            numero_mes = int(mes_texto)

            movimientos_bancarios = [
                m
                for m in movimientos_bancarios
                if (
                    m.fecha
                    and m.fecha.year == anio
                    and m.fecha.month == numero_mes
                )
            ]

        except (ValueError, TypeError):
            pass

    if cuenta_filtro:
        movimientos_bancarios = [
            m
            for m in movimientos_bancarios
            if (
                _nombre_cuenta_valido(m.cuenta) == cuenta_filtro
                or _nombre_cuenta_valido(m.cuenta_destino) == cuenta_filtro
            )
        ]

    entradas_periodo = 0.0
    salidas_periodo = 0.0
    transferencias_periodo = 0.0
    sin_conciliar_periodo = 0

    for m in movimientos_bancarios:
        tipo = str(m.tipo or "").strip().upper()
        valor = _valor_movimiento_bancario(m)

        if tipo == "INGRESO":
            entradas_periodo += valor

        elif tipo == "SALDO INICIAL CUENTA":
            entradas_periodo += valor

        elif tipo == "TRANSFERENCIA":
            transferencias_periodo += valor

        else:
            salidas_periodo += valor

        if not bool(m.revisado):
            sin_conciliar_periodo += 1

    saldo_total = sum(
        float(c["saldo"] or 0)
        for c in cuentas
    )

    return render_template(
        "contabilidad/crv_bancos_caja.html",
        empresa_nombre=empresa_nombre,
        cuentas=cuentas,
        movimientos=movimientos_bancarios,
        mes_actual=mes,
        cuenta_actual=cuenta_filtro,
        saldo_total=saldo_total,
        entradas_periodo=entradas_periodo,
        salidas_periodo=salidas_periodo,
        transferencias_periodo=transferencias_periodo,
        sin_conciliar_periodo=sin_conciliar_periodo
    )

@crv_bp.route(
    "/bancos-caja/conciliar/<int:movimiento_id>",
    methods=["POST"]
)
def bancos_caja_conciliar(movimiento_id):

    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    movimiento = CRVMovimiento.query.get_or_404(
        movimiento_id
    )

    if movimiento.empresa_id != empresa_id:
        return redirect("/crv/bancos-caja")

    if not _movimiento_es_bancario(movimiento):
        flash(
            "Ese registro no corresponde a Bancos y caja.",
            "error"
        )
        return redirect("/crv/bancos-caja")

    movimiento.revisado = not bool(
        movimiento.revisado
    )

    db.session.commit()

    flash(
        "Estado de conciliación actualizado.",
        "success"
    )

    return redirect(
        request.referrer
        or "/crv/bancos-caja"
    )

@crv_bp.route(
    "/bancos-caja/eliminar/<int:movimiento_id>",
    methods=["POST"]
)
def bancos_caja_eliminar(movimiento_id):

    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    movimiento = CRVMovimiento.query.get_or_404(
        movimiento_id
    )

    if movimiento.empresa_id != empresa_id:
        return redirect("/crv/bancos-caja")

    if movimiento.origen_registro not in (
        "BANCOS_CAJA_SALDO_INICIAL",
        "BANCOS_CAJA_TRANSFERENCIA",
    ):
        flash(
            "Este movimiento proviene de otro módulo y debe corregirse desde su origen.",
            "warning"
        )
        return redirect("/crv/bancos-caja")

    try:
        db.session.delete(movimiento)
        db.session.commit()

        flash(
            "Registro bancario eliminado correctamente.",
            "success"
        )

    except Exception as error:
        db.session.rollback()
        flash(
            f"No fue posible eliminar el registro: {error}",
            "error"
        )

    return redirect("/crv/bancos-caja")

__all__ = ['bancos_caja', 'bancos_caja_conciliar', 'bancos_caja_eliminar']
