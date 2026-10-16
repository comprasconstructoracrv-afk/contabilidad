"""CRV Cierres routes."""

from .crv_core import (
    CRVCierreMensual,
    _cierre_periodo,
    _resumen_cierre_mes,
    crv_bp,
    date,
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
    "/cierre-mensual",
    methods=["GET", "POST"]
)
def cierre_mensual_crv():

    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get(
        "empresa_id"
    )

    empresa_nombre = session.get(
        "empresa_nombre",
        "CRV CONSTRUCTORA"
    )

    periodo = request.values.get(
        "periodo",
        ""
    ).strip()

    if not periodo:
        hoy = date.today()

        periodo = (
            f"{hoy.year}-"
            f"{hoy.month:02d}"
        )

    try:
        anio_texto, mes_texto = periodo.split(
            "-"
        )

        anio = int(
            anio_texto
        )

        mes = int(
            mes_texto
        )

        if mes < 1 or mes > 12:
            raise ValueError

    except (ValueError, TypeError):
        hoy = date.today()
        anio = hoy.year
        mes = hoy.month
        periodo = (
            f"{anio}-"
            f"{mes:02d}"
        )

    resumen = _resumen_cierre_mes(
        empresa_id,
        anio,
        mes
    )

    cierre = _cierre_periodo(
        empresa_id,
        anio,
        mes
    )

    if request.method == "POST":

        accion = request.form.get(
            "accion",
            ""
        ).strip().lower()

        if accion == "cerrar":

            if (
                cierre
                and cierre.estado
                == "CERRADO"
            ):
                flash(
                    "Este periodo ya se encuentra cerrado.",
                    "warning"
                )

                return redirect(
                    f"/crv/cierre-mensual?periodo={periodo}"
                )

            if not resumen[
                "puede_cerrar"
            ]:
                flash(
                    (
                        "No se puede cerrar el periodo mientras "
                        "existan movimientos bancarios sin conciliar."
                    ),
                    "error"
                )

                return redirect(
                    f"/crv/cierre-mensual?periodo={periodo}"
                )

            if not cierre:
                cierre = CRVCierreMensual(
                    empresa_id=empresa_id,
                    anio=anio,
                    mes=mes
                )

                db.session.add(
                    cierre
                )

            cierre.estado = "CERRADO"
            cierre.ingresos = resumen[
                "ingresos"
            ]
            cierre.compras = resumen[
                "compras"
            ]
            cierre.gastos = resumen[
                "gastos"
            ]
            cierre.resultado = resumen[
                "resultado"
            ]

            cierre.cxp_facturado = resumen[
                "cxp_facturado"
            ]
            cierre.cxp_pagado = resumen[
                "cxp_pagado"
            ]
            cierre.cxp_pendiente = resumen[
                "cxp_pendiente"
            ]

            cierre.cxc_facturado = resumen[
                "cxc_facturado"
            ]
            cierre.cxc_cobrado = resumen[
                "cxc_cobrado"
            ]
            cierre.cxc_pendiente = resumen[
                "cxc_pendiente"
            ]

            cierre.saldo_bancos_caja = resumen[
                "saldo_bancos_caja"
            ]

            cierre.movimientos_mes = resumen[
                "movimientos_mes"
            ]

            cierre.movimientos_sin_conciliar = resumen[
                "movimientos_sin_conciliar"
            ]

            cierre.observaciones = request.form.get(
                "observaciones",
                ""
            ).strip()

            cierre.usuario_cierre = str(
                session.get(
                    "usuario",
                    ""
                )
            )

            cierre.fecha_cierre = datetime.utcnow()

            try:
                db.session.commit()

                flash(
                    (
                        f"Periodo {periodo} cerrado correctamente. "
                        "Los registros contables del mes quedaron bloqueados."
                    ),
                    "success"
                )

            except Exception as error:
                db.session.rollback()

                flash(
                    f"No fue posible cerrar el periodo: {error}",
                    "error"
                )

            return redirect(
                f"/crv/cierre-mensual?periodo={periodo}"
            )

    cierres = (
        CRVCierreMensual.query
        .filter_by(
            empresa_id=empresa_id
        )
        .order_by(
            CRVCierreMensual.anio.desc(),
            CRVCierreMensual.mes.desc()
        )
        .all()
    )

    return render_template(
        "contabilidad/crv_cierre_mensual.html",
        empresa_nombre=empresa_nombre,
        periodo=periodo,
        anio=anio,
        mes=mes,
        resumen=resumen,
        cierre=cierre,
        cierres=cierres
    )

@crv_bp.route(
    "/cierre-mensual/<int:cierre_id>/reabrir",
    methods=["POST"]
)
def cierre_mensual_reabrir(
    cierre_id
):

    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get(
        "empresa_id"
    )

    cierre = (
        CRVCierreMensual.query
        .get_or_404(
            cierre_id
        )
    )

    if cierre.empresa_id != empresa_id:
        return redirect(
            "/crv/cierre-mensual"
        )

    motivo = request.form.get(
        "motivo_reapertura",
        ""
    ).strip()

    if not motivo:
        flash(
            (
                "Para reabrir un periodo debes indicar "
                "el motivo de la reapertura."
            ),
            "error"
        )

        return redirect(
            (
                "/crv/cierre-mensual?"
                f"periodo={cierre.anio}-{cierre.mes:02d}"
            )
        )

    cierre.estado = "ABIERTO"

    cierre.usuario_reapertura = str(
        session.get(
            "usuario",
            ""
        )
    )

    cierre.fecha_reapertura = datetime.utcnow()

    cierre.motivo_reapertura = motivo

    db.session.commit()

    flash(
        (
            f"Periodo {cierre.anio}-{cierre.mes:02d} "
            "reabierto. Ya se pueden realizar correcciones."
        ),
        "success"
    )

    return redirect(
        (
            "/crv/cierre-mensual?"
            f"periodo={cierre.anio}-{cierre.mes:02d}"
        )
    )

__all__ = ['cierre_mensual_crv', 'cierre_mensual_reabrir']
