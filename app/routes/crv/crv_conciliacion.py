"""CRV Conciliacion routes."""

from .crv_core import (
    CRVConciliacionBancaria,
    CRVMovimiento,
    _conciliacion_periodo,
    _cuentas_financieras_crv,
    _impacto_bancario_movimiento,
    _movimientos_cuenta_periodo,
    _rango_mes,
    _saldo_cuenta_hasta,
    convertir_numero,
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
    "/conciliacion-bancaria",
    methods=["GET", "POST"]
)
def conciliacion_bancaria_crv():

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

    cuentas_data = _cuentas_financieras_crv(
        empresa_id
    )

    cuentas = [
        c["nombre"]
        for c in cuentas_data
    ]

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
        anio_texto, mes_texto = periodo.split("-")
        anio = int(anio_texto)
        mes = int(mes_texto)

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

    cuenta = request.values.get(
        "cuenta",
        ""
    ).strip()

    if not cuenta and cuentas:
        cuenta = cuentas[0]

    if cuenta and cuenta not in cuentas:
        cuenta = (
            cuentas[0]
            if cuentas
            else ""
        )

    fecha_inicio, fecha_fin = _rango_mes(
        anio,
        mes
    )

    movimientos = []

    saldo_sistema = 0.0
    saldo_extracto = None
    diferencia = None
    conciliacion = None

    if cuenta:
        movimientos = _movimientos_cuenta_periodo(
            empresa_id,
            cuenta,
            anio,
            mes
        )

        saldo_sistema = _saldo_cuenta_hasta(
            empresa_id,
            cuenta,
            fecha_fin
        )

        conciliacion = _conciliacion_periodo(
            empresa_id,
            cuenta,
            anio,
            mes
        )

        if conciliacion:
            saldo_extracto = float(
                conciliacion.saldo_extracto
                or 0
            )

            diferencia = (
                saldo_extracto
                - saldo_sistema
            )

    if request.method == "POST":

        accion = request.form.get(
            "accion",
            ""
        ).strip().lower()

        if accion == "guardar_extracto":

            if not cuenta:
                flash(
                    "Debes seleccionar una cuenta propia de CRV.",
                    "error"
                )

                return redirect(
                    f"/crv/conciliacion-bancaria?periodo={periodo}"
                )

            saldo_extracto = convertir_numero(
                request.form.get(
                    "saldo_extracto"
                )
            )

            observaciones = request.form.get(
                "observaciones",
                ""
            ).strip()

            if not conciliacion:
                conciliacion = CRVConciliacionBancaria(
                    empresa_id=empresa_id,
                    cuenta=cuenta,
                    anio=anio,
                    mes=mes
                )

                db.session.add(
                    conciliacion
                )

            conciliacion.saldo_extracto = saldo_extracto
            conciliacion.saldo_sistema = saldo_sistema
            conciliacion.diferencia = (
                saldo_extracto
                - saldo_sistema
            )

            conciliacion.observaciones = observaciones
            conciliacion.usuario_registro = str(
                session.get(
                    "usuario",
                    ""
                )
            )

            pendientes = [
                m
                for m in movimientos
                if not bool(m.revisado)
            ]

            if (
                abs(
                    conciliacion.diferencia
                ) < 0.01
                and not pendientes
            ):
                conciliacion.estado = "CONCILIADA"
                conciliacion.fecha_conciliacion = datetime.utcnow()

            else:
                conciliacion.estado = "PENDIENTE"
                conciliacion.fecha_conciliacion = None

            db.session.commit()

            flash(
                "Saldo del extracto guardado correctamente.",
                "success"
            )

            return redirect(
                (
                    "/crv/conciliacion-bancaria?"
                    f"periodo={periodo}"
                    f"&cuenta={cuenta}"
                )
            )

    pendientes = [
        m
        for m in movimientos
        if not bool(m.revisado)
    ]

    conciliados = [
        m
        for m in movimientos
        if bool(m.revisado)
    ]

    entradas = sum(
        max(
            0,
            _impacto_bancario_movimiento(
                m,
                cuenta
            )
        )
        for m in movimientos
    ) if cuenta else 0

    salidas = sum(
        abs(
            min(
                0,
                _impacto_bancario_movimiento(
                    m,
                    cuenta
                )
            )
        )
        for m in movimientos
    ) if cuenta else 0

    return render_template(
        "contabilidad/crv_conciliacion_bancaria.html",
        empresa_nombre=empresa_nombre,
        cuentas=cuentas,
        cuenta_actual=cuenta,
        periodo=periodo,
        anio=anio,
        mes=mes,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        movimientos=movimientos,
        pendientes=pendientes,
        conciliados=conciliados,
        entradas=entradas,
        salidas=salidas,
        saldo_sistema=saldo_sistema,
        saldo_extracto=saldo_extracto,
        diferencia=diferencia,
        extracto_registrado=bool(conciliacion),
        conciliacion=conciliacion
    )

@crv_bp.route(
    "/conciliacion-bancaria/movimiento/<int:movimiento_id>",
    methods=["POST"]
)
def conciliacion_bancaria_movimiento(
    movimiento_id
):

    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get(
        "empresa_id"
    )

    movimiento = (
        CRVMovimiento.query
        .get_or_404(
            movimiento_id
        )
    )

    if movimiento.empresa_id != empresa_id:
        return redirect(
            "/crv/conciliacion-bancaria"
        )

    periodo = request.form.get(
        "periodo",
        ""
    ).strip()

    cuenta = request.form.get(
        "cuenta",
        ""
    ).strip()

    movimiento.revisado = not bool(
        movimiento.revisado
    )

    db.session.commit()

    flash(
        (
            "Movimiento marcado como conciliado."
            if movimiento.revisado
            else "Movimiento devuelto a pendiente."
        ),
        "success"
    )

    return redirect(
        (
            "/crv/conciliacion-bancaria?"
            f"periodo={periodo}"
            f"&cuenta={cuenta}"
        )
    )

@crv_bp.route(
    "/conciliacion-bancaria/conciliar-todo",
    methods=["POST"]
)
def conciliacion_bancaria_todo():

    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get(
        "empresa_id"
    )

    periodo = request.form.get(
        "periodo",
        ""
    ).strip()

    cuenta = request.form.get(
        "cuenta",
        ""
    ).strip()

    try:
        anio, mes = [
            int(x)
            for x in periodo.split("-")
        ]
    except (ValueError, TypeError):
        flash(
            "Periodo inválido.",
            "error"
        )

        return redirect(
            "/crv/conciliacion-bancaria"
        )

    movimientos = _movimientos_cuenta_periodo(
        empresa_id,
        cuenta,
        anio,
        mes
    )

    for movimiento in movimientos:
        movimiento.revisado = True

    _, fecha_fin = _rango_mes(
        anio,
        mes
    )

    saldo_sistema = _saldo_cuenta_hasta(
        empresa_id,
        cuenta,
        fecha_fin
    )

    conciliacion = _conciliacion_periodo(
        empresa_id,
        cuenta,
        anio,
        mes
    )

    if conciliacion:
        conciliacion.saldo_sistema = saldo_sistema
        conciliacion.diferencia = (
            float(
                conciliacion.saldo_extracto
                or 0
            )
            - saldo_sistema
        )

        if abs(
            conciliacion.diferencia
        ) < 0.01:
            conciliacion.estado = "CONCILIADA"
            conciliacion.fecha_conciliacion = datetime.utcnow()

    db.session.commit()

    flash(
        "Todos los movimientos de la cuenta y periodo fueron marcados como conciliados.",
        "success"
    )

    return redirect(
        (
            "/crv/conciliacion-bancaria?"
            f"periodo={periodo}"
            f"&cuenta={cuenta}"
        )
    )

__all__ = ['conciliacion_bancaria_crv', 'conciliacion_bancaria_movimiento', 'conciliacion_bancaria_todo']
