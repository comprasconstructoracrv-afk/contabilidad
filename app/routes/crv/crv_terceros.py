"""CRV Terceros routes."""

from .crv_core import (
    CRVTercero,
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
    "/terceros",
    methods=["GET", "POST"]
)
def terceros():

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    empresa_nombre = session.get(
        "empresa_nombre",
        "CRV CONSTRUCTORA"
    )

    if request.method == "POST":

        identificacion = request.form.get(
            "identificacion",
            ""
        ).strip()

        razon_social = request.form.get(
            "razon_social",
            ""
        ).strip()

        if not identificacion:

            flash(
                "La identificación del tercero es obligatoria.",
                "error"
            )

            return redirect(
                "/crv/terceros"
            )

        if not razon_social:

            flash(
                "El nombre o razón social es obligatorio.",
                "error"
            )

            return redirect(
                "/crv/terceros"
            )

        existente = CRVTercero.query.filter_by(
            empresa_id=empresa_id,
            identificacion=identificacion
        ).first()

        if existente:

            flash(
                "Ya existe un tercero con esa identificación.",
                "error"
            )

            return redirect(
                "/crv/terceros"
            )

        tercero = CRVTercero(

            empresa_id=empresa_id,

            tipo_tercero=request.form.get(
                "tipo_tercero",
                "TERCERO"
            ).strip().upper(),

            tipo_documento=request.form.get(
                "tipo_documento",
                ""
            ).strip(),

            identificacion=identificacion,

            razon_social=razon_social,

            nombre_comercial=request.form.get(
                "nombre_comercial",
                ""
            ).strip(),

            direccion=request.form.get(
                "direccion",
                ""
            ).strip(),

            ciudad=request.form.get(
                "ciudad",
                ""
            ).strip(),

            departamento=request.form.get(
                "departamento",
                ""
            ).strip(),

            telefono=request.form.get(
                "telefono",
                ""
            ).strip(),

            celular=request.form.get(
                "celular",
                ""
            ).strip(),

            email=request.form.get(
                "email",
                ""
            ).strip(),

            contacto=request.form.get(
                "contacto",
                ""
            ).strip(),

            banco=request.form.get(
                "banco",
                ""
            ).strip(),

            tipo_cuenta=request.form.get(
                "tipo_cuenta",
                ""
            ).strip(),

            numero_cuenta=request.form.get(
                "numero_cuenta",
                ""
            ).strip(),

            titular_cuenta=request.form.get(
                "titular_cuenta",
                ""
            ).strip(),

            observaciones=request.form.get(
                "observaciones",
                ""
            ).strip(),

            activo=True
        )

        db.session.add(tercero)

        db.session.commit()

        flash(
            "Tercero creado correctamente.",
            "success"
        )

        return redirect(
            "/crv/terceros"
        )

    busqueda = request.args.get(
        "buscar",
        ""
    ).strip()

    query = CRVTercero.query.filter_by(
        empresa_id=empresa_id
    )

    if busqueda:

        patron = f"%{busqueda}%"

        query = query.filter(
            db.or_(
                CRVTercero.razon_social.ilike(
                    patron
                ),

                CRVTercero.identificacion.ilike(
                    patron
                ),

                CRVTercero.nombre_comercial.ilike(
                    patron
                )
            )
        )

    registros = query.order_by(
        CRVTercero.razon_social.asc()
    ).all()

    return render_template(
        "contabilidad/crv_terceros.html",

        empresa_nombre=empresa_nombre,

        terceros=registros,

        busqueda=busqueda
    )

@crv_bp.route(
    "/terceros/estado/<int:tercero_id>",
    methods=["POST"]
)
def cambiar_estado_tercero(tercero_id):

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    tercero = CRVTercero.query.get_or_404(
        tercero_id
    )

    if tercero.empresa_id != empresa_id:

        return redirect(
            "/crv/terceros"
        )

    tercero.activo = not tercero.activo

    db.session.commit()

    return redirect(
        "/crv/terceros"
    )

@crv_bp.route(
    "/terceros/editar/<int:tercero_id>",
    methods=["POST"]
)
def editar_tercero(tercero_id):

    bloqueo = proteger_crv()

    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")

    tercero = CRVTercero.query.get_or_404(
        tercero_id
    )

    # Seguridad:
    # solo permite modificar terceros pertenecientes
    # a la empresa CRV actualmente seleccionada.
    if tercero.empresa_id != empresa_id:

        flash(
            "No tienes permiso para modificar este tercero.",
            "error"
        )

        return redirect(
            "/crv/terceros"
        )

    identificacion = request.form.get(
        "identificacion",
        ""
    ).strip()

    razon_social = request.form.get(
        "razon_social",
        ""
    ).strip()

    # --------------------------------------------------------
    # VALIDACIONES
    # --------------------------------------------------------

    if not identificacion:

        flash(
            "La identificación del tercero es obligatoria.",
            "error"
        )

        return redirect(
            "/crv/terceros"
        )

    if not razon_social:

        flash(
            "El nombre o razón social es obligatorio.",
            "error"
        )

        return redirect(
            "/crv/terceros"
        )

    # Verificar que la nueva identificación no pertenezca
    # a otro tercero de la misma empresa.
    duplicado = CRVTercero.query.filter(
        CRVTercero.empresa_id == empresa_id,
        CRVTercero.identificacion == identificacion,
        CRVTercero.id != tercero.id
    ).first()

    if duplicado:

        flash(
            "Ya existe otro tercero con esa identificación.",
            "error"
        )

        return redirect(
            "/crv/terceros"
        )

    # --------------------------------------------------------
    # INFORMACIÓN GENERAL
    # --------------------------------------------------------

    tercero.tipo_tercero = request.form.get(
        "tipo_tercero",
        "TERCERO"
    ).strip().upper() or "TERCERO"

    tercero.tipo_documento = request.form.get(
        "tipo_documento",
        ""
    ).strip()

    tercero.identificacion = identificacion

    tercero.razon_social = razon_social

    tercero.nombre_comercial = request.form.get(
        "nombre_comercial",
        ""
    ).strip()

    # --------------------------------------------------------
    # INFORMACIÓN DE CONTACTO
    # --------------------------------------------------------

    tercero.direccion = request.form.get(
        "direccion",
        ""
    ).strip()

    tercero.ciudad = request.form.get(
        "ciudad",
        ""
    ).strip()

    tercero.departamento = request.form.get(
        "departamento",
        ""
    ).strip()

    tercero.telefono = request.form.get(
        "telefono",
        ""
    ).strip()

    tercero.celular = request.form.get(
        "celular",
        ""
    ).strip()

    tercero.email = request.form.get(
        "email",
        ""
    ).strip()

    tercero.contacto = request.form.get(
        "contacto",
        ""
    ).strip()

    # --------------------------------------------------------
    # INFORMACIÓN BANCARIA
    # --------------------------------------------------------

    tercero.banco = request.form.get(
        "banco",
        ""
    ).strip()

    tercero.tipo_cuenta = request.form.get(
        "tipo_cuenta",
        ""
    ).strip()

    tercero.numero_cuenta = request.form.get(
        "numero_cuenta",
        ""
    ).strip()

    tercero.titular_cuenta = request.form.get(
        "titular_cuenta",
        ""
    ).strip()

    # --------------------------------------------------------
    # INFORMACIÓN ADICIONAL
    # --------------------------------------------------------

    tercero.observaciones = request.form.get(
        "observaciones",
        ""
    ).strip()

    # --------------------------------------------------------
    # GUARDAR
    # --------------------------------------------------------

    try:

        db.session.commit()

        flash(
            "Datos del tercero actualizados correctamente.",
            "success"
        )

    except Exception:

        db.session.rollback()

        flash(
            "No fue posible actualizar el tercero.",
            "error"
        )

    return redirect(
        "/crv/terceros"
    )

__all__ = ['terceros', 'cambiar_estado_tercero', 'editar_tercero']
