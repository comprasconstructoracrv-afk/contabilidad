"""CRV Proyectos routes."""

from .crv_core import (
    CRVProyecto,
    _clientes_proyectos_crv,
    _cuentas_cobrar_proyecto,
    _cuentas_pagar_proyecto,
    _movimientos_proyecto,
    _resumen_proyecto,
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

@crv_bp.route(
    "/proyectos",
    methods=["GET", "POST"]
)
def proyectos_crv():

    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get(
        "empresa_nombre",
        "CRV CONSTRUCTORA"
    )

    if request.method == "POST":

        codigo = request.form.get(
            "codigo",
            ""
        ).strip().upper()

        nombre = request.form.get(
            "nombre",
            ""
        ).strip().upper()

        if not codigo or not nombre:
            flash(
                "Código y nombre del proyecto son obligatorios.",
                "error"
            )
            return redirect("/crv/proyectos")

        existe_codigo = (
            CRVProyecto.query
            .filter_by(
                empresa_id=empresa_id,
                codigo=codigo
            )
            .first()
        )

        if existe_codigo:
            flash(
                "Ya existe un proyecto con ese código.",
                "error"
            )
            return redirect("/crv/proyectos")

        existe_nombre = (
            CRVProyecto.query
            .filter(
                CRVProyecto.empresa_id == empresa_id,
                db.func.lower(
                    CRVProyecto.nombre
                ) == nombre.lower()
            )
            .first()
        )

        if existe_nombre:
            flash(
                "Ya existe un proyecto con ese nombre.",
                "error"
            )
            return redirect("/crv/proyectos")

        cliente_texto = request.form.get(
            "cliente_id",
            ""
        ).strip()

        cliente_id = (
            int(cliente_texto)
            if cliente_texto.isdigit()
            else None
        )

        proyecto = CRVProyecto(
            empresa_id=empresa_id,
            codigo=codigo,
            nombre=nombre,
            tipo=request.form.get(
                "tipo",
                ""
            ).strip().upper(),
            cliente_id=cliente_id,
            ubicacion=request.form.get(
                "ubicacion",
                ""
            ).strip(),
            fecha_inicio=convertir_fecha(
                request.form.get(
                    "fecha_inicio"
                )
            ),
            fecha_fin_estimada=convertir_fecha(
                request.form.get(
                    "fecha_fin_estimada"
                )
            ),
            presupuesto=convertir_numero(
                request.form.get(
                    "presupuesto"
                )
            ),
            valor_contrato=convertir_numero(
                request.form.get(
                    "valor_contrato"
                )
            ),
            responsable=request.form.get(
                "responsable",
                ""
            ).strip(),
            centro_costo=request.form.get(
                "centro_costo",
                ""
            ).strip(),
            estado=request.form.get(
                "estado",
                "ACTIVO"
            ).strip().upper() or "ACTIVO",
            descripcion=request.form.get(
                "descripcion",
                ""
            ).strip(),
            observaciones=request.form.get(
                "observaciones",
                ""
            ).strip(),
            activo=True,
            usuario_registro=str(
                session.get(
                    "usuario",
                    ""
                )
            )
        )

        try:
            db.session.add(proyecto)
            db.session.commit()

            flash(
                "Proyecto registrado correctamente.",
                "success"
            )

            return redirect(
                f"/crv/proyectos/{proyecto.id}"
            )

        except Exception as error:
            db.session.rollback()

            flash(
                f"No fue posible registrar el proyecto: {error}",
                "error"
            )

            return redirect("/crv/proyectos")

    buscar = request.args.get(
        "buscar",
        ""
    ).strip()

    estado = request.args.get(
        "estado",
        ""
    ).strip().upper()

    query = CRVProyecto.query.filter_by(
        empresa_id=empresa_id
    )

    if estado:
        query = query.filter_by(
            estado=estado
        )

    proyectos = query.order_by(
        CRVProyecto.activo.desc(),
        CRVProyecto.nombre.asc()
    ).all()

    if buscar:
        texto = buscar.lower()

        proyectos = [
            p for p in proyectos
            if (
                texto in (p.codigo or "").lower()
                or texto in (p.nombre or "").lower()
                or texto in (p.ubicacion or "").lower()
                or texto in (p.responsable or "").lower()
                or texto in (
                    (
                        p.cliente.razon_social
                        if p.cliente
                        else ""
                    ).lower()
                )
            )
        ]

    filas = []

    total_presupuesto = 0.0
    total_costos = 0.0
    total_ingresos = 0.0
    total_resultado = 0.0

    for proyecto in proyectos:
        resumen = _resumen_proyecto(
            proyecto
        )

        filas.append({
            "proyecto": proyecto,
            "resumen": resumen
        })

        total_presupuesto += float(
            proyecto.presupuesto or 0
        )

        total_costos += resumen[
            "costos"
        ]

        total_ingresos += resumen[
            "ingresos"
        ]

        total_resultado += resumen[
            "resultado"
        ]

    db.session.commit()

    return render_template(
        "contabilidad/crv_proyectos.html",
        empresa_nombre=empresa_nombre,
        filas=filas,
        clientes=_clientes_proyectos_crv(
            empresa_id
        ),
        buscar_actual=buscar,
        estado_actual=estado,
        total_proyectos=len(proyectos),
        total_presupuesto=total_presupuesto,
        total_costos=total_costos,
        total_ingresos=total_ingresos,
        total_resultado=total_resultado
    )

@crv_bp.route(
    "/proyectos/<int:proyecto_id>"
)
def proyecto_detalle_crv(proyecto_id):

    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    proyecto = (
        CRVProyecto.query
        .get_or_404(
            proyecto_id
        )
    )

    if proyecto.empresa_id != empresa_id:
        return redirect(
            "/crv/proyectos"
        )

    resumen = _resumen_proyecto(
        proyecto
    )

    db.session.commit()

    return render_template(
        "contabilidad/crv_proyecto_detalle.html",
        empresa_nombre=session.get(
            "empresa_nombre",
            "CRV CONSTRUCTORA"
        ),
        proyecto=proyecto,
        resumen=resumen
    )

@crv_bp.route(
    "/proyectos/<int:proyecto_id>/editar",
    methods=["POST"]
)
def proyecto_editar_crv(proyecto_id):

    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    proyecto = (
        CRVProyecto.query
        .get_or_404(
            proyecto_id
        )
    )

    if proyecto.empresa_id != empresa_id:
        return redirect(
            "/crv/proyectos"
        )

    nombre_anterior = proyecto.nombre

    codigo = request.form.get(
        "codigo",
        ""
    ).strip().upper()

    nombre = request.form.get(
        "nombre",
        ""
    ).strip().upper()

    if not codigo or not nombre:
        flash(
            "Código y nombre son obligatorios.",
            "error"
        )
        return redirect(
            f"/crv/proyectos/{proyecto.id}"
        )

    duplicado_codigo = (
        CRVProyecto.query
        .filter(
            CRVProyecto.empresa_id == empresa_id,
            CRVProyecto.codigo == codigo,
            CRVProyecto.id != proyecto.id
        )
        .first()
    )

    if duplicado_codigo:
        flash(
            "Ya existe otro proyecto con ese código.",
            "error"
        )
        return redirect(
            f"/crv/proyectos/{proyecto.id}"
        )

    cliente_texto = request.form.get(
        "cliente_id",
        ""
    ).strip()

    proyecto.codigo = codigo
    proyecto.nombre = nombre
    proyecto.tipo = request.form.get(
        "tipo",
        ""
    ).strip().upper()

    proyecto.cliente_id = (
        int(cliente_texto)
        if cliente_texto.isdigit()
        else None
    )

    proyecto.ubicacion = request.form.get(
        "ubicacion",
        ""
    ).strip()

    proyecto.fecha_inicio = convertir_fecha(
        request.form.get(
            "fecha_inicio"
        )
    )

    proyecto.fecha_fin_estimada = convertir_fecha(
        request.form.get(
            "fecha_fin_estimada"
        )
    )

    proyecto.presupuesto = convertir_numero(
        request.form.get(
            "presupuesto"
        )
    )

    proyecto.valor_contrato = convertir_numero(
        request.form.get(
            "valor_contrato"
        )
    )

    proyecto.responsable = request.form.get(
        "responsable",
        ""
    ).strip()

    proyecto.centro_costo = request.form.get(
        "centro_costo",
        ""
    ).strip()

    proyecto.estado = request.form.get(
        "estado",
        "ACTIVO"
    ).strip().upper() or "ACTIVO"

    proyecto.descripcion = request.form.get(
        "descripcion",
        ""
    ).strip()

    proyecto.observaciones = request.form.get(
        "observaciones",
        ""
    ).strip()

    # Si se cambia el nombre, trasladamos la clasificación histórica
    # de todos los registros vinculados al nombre anterior.
    if (
        nombre_anterior
        and nombre_anterior.strip().lower()
        != nombre.strip().lower()
    ):

        for movimiento in _movimientos_proyecto(
            empresa_id,
            nombre_anterior
        ):
            movimiento.proyecto = nombre

        for cuenta in _cuentas_pagar_proyecto(
            empresa_id,
            nombre_anterior
        ):
            cuenta.proyecto = nombre

        for cuenta in _cuentas_cobrar_proyecto(
            empresa_id,
            nombre_anterior
        ):
            cuenta.proyecto = nombre

    try:
        db.session.commit()

        flash(
            "Proyecto actualizado correctamente.",
            "success"
        )

    except Exception as error:
        db.session.rollback()

        flash(
            f"No fue posible actualizar el proyecto: {error}",
            "error"
        )

    return redirect(
        f"/crv/proyectos/{proyecto.id}"
    )

@crv_bp.route(
    "/proyectos/<int:proyecto_id>/estado",
    methods=["POST"]
)
def proyecto_estado_crv(proyecto_id):

    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    proyecto = (
        CRVProyecto.query
        .get_or_404(
            proyecto_id
        )
    )

    if proyecto.empresa_id != empresa_id:
        return redirect(
            "/crv/proyectos"
        )

    proyecto.activo = not bool(
        proyecto.activo
    )

    if not proyecto.activo:
        proyecto.estado = "ARCHIVADO"

    elif proyecto.estado == "ARCHIVADO":
        proyecto.estado = "ACTIVO"

    db.session.commit()

    flash(
        (
            "Proyecto reactivado correctamente."
            if proyecto.activo
            else "Proyecto archivado correctamente."
        ),
        "success"
    )

    return redirect(
        request.referrer
        or "/crv/proyectos"
    )

@crv_bp.route(
    "/proyectos/<int:proyecto_id>/eliminar",
    methods=["POST"]
)
def proyecto_eliminar_crv(proyecto_id):

    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    proyecto = (
        CRVProyecto.query
        .get_or_404(
            proyecto_id
        )
    )

    if proyecto.empresa_id != empresa_id:
        return redirect(
            "/crv/proyectos"
        )

    resumen = _resumen_proyecto(
        proyecto
    )

    if (
        resumen["movimientos"]
        or resumen["cuentas_pagar"]
        or resumen["cuentas_cobrar"]
    ):
        flash(
            "No se puede eliminar un proyecto con información contable. "
            "Puedes archivarlo para conservar la trazabilidad.",
            "warning"
        )

        return redirect(
            f"/crv/proyectos/{proyecto.id}"
        )

    try:
        db.session.delete(
            proyecto
        )

        db.session.commit()

        flash(
            "Proyecto eliminado correctamente.",
            "success"
        )

    except Exception as error:
        db.session.rollback()

        flash(
            f"No fue posible eliminar el proyecto: {error}",
            "error"
        )

    return redirect(
        "/crv/proyectos"
    )

__all__ = ['proyectos_crv', 'proyecto_detalle_crv', 'proyecto_editar_crv', 'proyecto_estado_crv', 'proyecto_eliminar_crv']
