"""CRV Perfil Cliente routes."""

from sqlalchemy import or_

from .crv_core import (
    CRVCuentaCobrar,
    CRVMovimiento,
    CRVTercero,
    crv_bp,
    proteger_crv,
    render_template,
    request,
    session,
)


@crv_bp.route("/perfil-cliente", methods=["GET"])
def perfil_cliente_crv():
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "CRV CONSTRUCTORA")

    cliente_id_raw = (request.args.get("cliente_id") or "").strip()
    buscar = (request.args.get("buscar") or "").strip()
    proyecto = (request.args.get("proyecto") or "").strip()

    clientes = (
        CRVTercero.query.filter(
            CRVTercero.empresa_id == empresa_id,
            CRVTercero.activo == True,
            CRVTercero.tipo_tercero.in_(["CLIENTE", "CLIENTE_ECOBIKE"]),
        )
        .order_by(CRVTercero.razon_social.asc())
        .all()
    )

    cliente_seleccionado = None
    if cliente_id_raw.isdigit():
        cliente_seleccionado = CRVTercero.query.filter_by(
            id=int(cliente_id_raw),
            empresa_id=empresa_id,
        ).first()
    elif buscar:
        cliente_seleccionado = (
            CRVTercero.query.filter(
                CRVTercero.empresa_id == empresa_id,
                or_(
                    CRVTercero.razon_social.ilike(f"%{buscar}%"),
                    CRVTercero.identificacion.ilike(f"%{buscar}%"),
                ),
            )
            .order_by(CRVTercero.razon_social.asc())
            .first()
        )

    movimientos = []
    ns_capital = 0.0
    ns_intereses = 0.0
    ns_mora = 0.0
    saldo_pendiente = 0.0
    resumen_negocio = None

    if cliente_seleccionado or buscar or proyecto:
        query = CRVMovimiento.query.filter(
            CRVMovimiento.empresa_id == empresa_id,
            CRVMovimiento.estado == "ACTIVO",
            CRVMovimiento.tipo.in_(["INGRESO", "COBRO CUENTA POR COBRAR"]),
            ~CRVMovimiento.origen_registro.like("CUENTA_POR_COBRAR:%"),
        )

        if cliente_seleccionado:
            condiciones_cliente = [CRVMovimiento.tercero_id == cliente_seleccionado.id]
            if cliente_seleccionado.identificacion:
                condiciones_cliente.append(
                    CRVMovimiento.tercero_identificacion == cliente_seleccionado.identificacion
                )
            query = query.filter(or_(*condiciones_cliente))
        elif buscar:
            query = query.filter(
                or_(
                    CRVMovimiento.tercero_nombre.ilike(f"%{buscar}%"),
                    CRVMovimiento.tercero_identificacion.ilike(f"%{buscar}%"),
                )
            )

        if proyecto:
            query = query.filter(
                or_(
                    CRVMovimiento.proyecto.ilike(f"%{proyecto}%"),
                    CRVMovimiento.obra.ilike(f"%{proyecto}%"),
                    CRVMovimiento.concepto.ilike(f"%{proyecto}%"),
                )
            )

        movimientos = query.order_by(
            CRVMovimiento.fecha.asc(),
            CRVMovimiento.id.asc(),
        ).all()

        for m in movimientos:
            cap = float(
                m.base_gravable
                if m.base_gravable is not None
                else (m.valor_neto or m.valor or 0)
            )
            inte = float(m.valor_intereses or 0)
            mora = float(m.valor_mora or 0)

            ns_capital += cap
            ns_intereses += inte
            ns_mora += mora

        if cliente_seleccionado:
            cxc_query = CRVCuentaCobrar.query.filter_by(
                empresa_id=empresa_id,
                cliente_id=cliente_seleccionado.id,
            )
            if proyecto:
                cxc_query = cxc_query.filter(
                    or_(
                        CRVCuentaCobrar.proyecto.ilike(f"%{proyecto}%"),
                        CRVCuentaCobrar.obra.ilike(f"%{proyecto}%"),
                        CRVCuentaCobrar.concepto.ilike(f"%{proyecto}%"),
                    )
                )

            cuentas = cxc_query.all()
            if cuentas:
                valor_total_cxc = sum(
                    float(c.valor_neto or c.valor_bruto or 0) for c in cuentas
                )
                saldo_pendiente = sum(
                    float(c.saldo_pendiente or 0) for c in cuentas
                )
                resumen_negocio = {
                    "valor_total": round(valor_total_cxc, 2),
                    "valor_inicial": round(ns_capital, 2),
                    "saldo_credito": round(saldo_pendiente, 2),
                }

    return render_template(
        "contabilidad/crv_perfil_cliente.html",
        empresa_nombre=empresa_nombre,
        clientes=clientes,
        cliente_seleccionado=cliente_seleccionado,
        buscar=buscar,
        proyecto=proyecto,
        movimientos=movimientos,
        ns_capital=round(ns_capital, 2),
        ns_intereses=round(ns_intereses, 2),
        ns_mora=round(ns_mora, 2),
        saldo_pendiente=round(saldo_pendiente, 2),
        resumen_negocio=resumen_negocio,
    )