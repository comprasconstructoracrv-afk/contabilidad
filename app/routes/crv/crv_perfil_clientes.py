from datetime import datetime
from flask import render_template, request, redirect, url_for, session, flash
from sqlalchemy import or_

from . import crv_bp
from app.extensions import db
from app.models.crv import (
    CRVTercero,
    CRVMovimiento,
    CRVCuentaCobrar,
    CRVPerfilCliente,
    CRVPerfilClienteItem,
    CRVPerfilClienteAdicional,
)


TIPOS_CONCEPTO_BASE = [
    ("VALOR_LOTE", "Valor Lote"),
    ("VALOR_CASA", "Valor Casa"),
    ("CONSTRUCCION", "Construcción"),
    ("MULTIPLE", "Múltiples conceptos (Lote + Casa / Construcción)"),
    ("OTRO", "Otro concepto"),
]


def proteger_crv():
    if "usuario_id" not in session:
        return redirect("/login")
    if session.get("empresa_modulo") != "crv":
        return redirect("/empresas")
    return None


def _parse_float(raw, default=0.0):
    if raw is None:
        return default
    txt = str(raw).strip().replace("$", "").replace(" ", "")
    if not txt:
        return default
    if "," in txt and "." in txt:
        if txt.rfind(",") > txt.rfind("."):
            txt = txt.replace(".", "").replace(",", ".")
        else:
            txt = txt.replace(",", "")
    elif "," in txt:
        partes = txt.split(",")
        if len(partes[-1]) == 3 and len(partes[0]) >= 1:
            txt = txt.replace(",", "")
        else:
            txt = txt.replace(",", ".")
    try:
        return float(txt)
    except ValueError:
        return default


def _extraer_conceptos_base_formulario(form):
    nombres = form.getlist("base_concepto[]")
    valores = form.getlist("base_valor[]")
    items = []
    for idx, nombre in enumerate(nombres):
        concepto = (nombre or "").strip()
        val = _parse_float(valores[idx] if idx < len(valores) else 0, 0.0)
        if concepto and val > 0:
            items.append(
                {
                    "orden": len(items) + 1,
                    "concepto": concepto,
                    "valor": round(val, 2),
                }
            )
    return items


def _extraer_tramos_formulario(form):
    nombres = form.getlist("tramo_concepto[]")
    porcentajes = form.getlist("tramo_porcentaje[]")
    tramos = []
    for idx, pct_raw in enumerate(porcentajes):
        pct = _parse_float(pct_raw, 0.0)
        nombre = (nombres[idx] if idx < len(nombres) else "").strip()
        if pct > 0:
            if not nombre:
                nombre = f"Tramo {len(tramos) + 1} ({pct:g}%)"
            tramos.append(
                {
                    "orden": len(tramos) + 1,
                    "concepto": nombre,
                    "porcentaje": round(pct, 4),
                }
            )
    return tramos


def _extraer_adicionales_formulario(form):
    nombres = form.getlist("adicional_concepto[]")
    valores = form.getlist("adicional_valor[]")
    adicionales = []
    for idx, nombre in enumerate(nombres):
        concepto = (nombre or "").strip()
        val = _parse_float(valores[idx] if idx < len(valores) else 0, 0.0)
        if concepto and val > 0:
            adicionales.append(
                {
                    "orden": len(adicionales) + 1,
                    "concepto": concepto,
                    "valor": round(val, 2),
                }
            )
    return adicionales


def _calcular_estructura_perfil(perfil):
    items_base = [
        it for it in perfil.items if (it.categoria or "").upper() == "BASE"
    ]
    items_tramo = [
        it for it in perfil.items if (it.categoria or "").upper() == "TRAMO"
    ]

    if items_base:
        conceptos_base = [
            {
                "id": it.id,
                "orden": it.orden,
                "concepto": it.concepto,
                "valor": round(float(it.valor or 0.0), 2),
            }
            for it in items_base
        ]
    else:
        conceptos_base = [
            {
                "id": None,
                "orden": 1,
                "concepto": perfil.concepto_base_label or "Valor Base",
                "valor": round(float(perfil.valor_base or 0.0), 2),
            }
        ]

    total_base = round(sum(c["valor"] for c in conceptos_base), 2)

    # Modo de aplicación de porcentajes: TODOS o SOLO_CONCEPTO:<indice_0_based>
    modo_raw = (perfil.tipo_concepto_base or "").strip()
    aplica_a_indice = None
    if modo_raw.startswith("SOLO_CONCEPTO:"):
        idx_str = modo_raw.split(":", 1)[1].strip()
        if idx_str.isdigit():
            idx_val = int(idx_str)
            if 0 <= idx_val < len(conceptos_base):
                aplica_a_indice = idx_val

    if aplica_a_indice is not None:
        base_para_tramos = conceptos_base[aplica_a_indice]["valor"]
        concepto_tramos_objetivo = conceptos_base[aplica_a_indice]["concepto"]
    else:
        base_para_tramos = total_base
        concepto_tramos_objetivo = None

    if items_tramo:
        tramos = []
        for it in items_tramo:
            pct = float(it.porcentaje or 0.0)
            monto = (
                round(base_para_tramos * (pct / 100.0), 2)
                if pct > 0
                else round(float(it.valor or 0.0), 2)
            )
            tramos.append(
                {
                    "id": it.id,
                    "orden": it.orden,
                    "concepto": it.concepto,
                    "porcentaje": pct,
                    "monto": monto,
                }
            )
    else:
        pct1 = float(perfil.porcentaje_tramo_1 or 0.0)
        pct2 = float(perfil.porcentaje_tramo_2 or 0.0)
        tramos = [
            {
                "id": None,
                "orden": 1,
                "concepto": f"Tramo 1 ({pct1:g}%)",
                "porcentaje": pct1,
                "monto": round(base_para_tramos * (pct1 / 100.0), 2),
            }
        ]
        if pct2 > 0:
            tramos.append(
                {
                    "id": None,
                    "orden": 2,
                    "concepto": f"Tramo 2 ({pct2:g}%)",
                    "porcentaje": pct2,
                    "monto": round(base_para_tramos * (pct2 / 100.0), 2),
                }
            )

    # Conceptos base que NO entran en el porcentaje (ej. Construcción de la casa)
    conceptos_sin_tramo = []
    if aplica_a_indice is not None:
        for idx, cb in enumerate(conceptos_base):
            if idx != aplica_a_indice:
                conceptos_sin_tramo.append(cb)

    adicionales = [
        {
            "id": ad.id,
            "orden": ad.orden,
            "concepto": ad.concepto,
            "valor": round(float(ad.valor or 0.0), 2),
        }
        for ad in perfil.adicionales
    ]
    total_adicionales = round(sum(a["valor"] for a in adicionales), 2)
    descuento = round(float(perfil.descuento or 0.0), 2)

    total_proyecto = round(
        max(0.0, total_base + total_adicionales - descuento),
        2,
    )

    return {
        "conceptos_base": conceptos_base,
        "total_base": total_base,
        "aplica_a_indice": aplica_a_indice,
        "concepto_tramos_objetivo": concepto_tramos_objetivo,
        "base_para_tramos": round(base_para_tramos, 2),
        "conceptos_sin_tramo": conceptos_sin_tramo,
        "tramos": tramos,
        "adicionales": adicionales,
        "total_adicionales": total_adicionales,
        "descuento": descuento,
        "total_proyecto": total_proyecto,
    }


def _aplicar_liberacion_cronologica(estructura, movimientos):
    bloques = []
    for idx, tr in enumerate(estructura["tramos"], start=1):
        bloques.append(
            {
                "tipo": "TRAMO",
                "orden": idx,
                "titulo": tr["concepto"],
                "objetivo": float(tr["monto"] or 0.0),
                "cubierto": 0.0,
            }
        )

    for idx, cb_libre in enumerate(estructura.get("conceptos_sin_tramo", []), start=1):
        bloques.append(
            {
                "tipo": "CONCEPTO_DIRECTO",
                "orden": idx,
                "titulo": cb_libre["concepto"],
                "objetivo": float(cb_libre["valor"] or 0.0),
                "cubierto": 0.0,
            }
        )

    for ad in estructura["adicionales"]:
        bloques.append(
            {
                "tipo": "ADICIONAL",
                "orden": ad["orden"],
                "titulo": f"Adicional {ad['orden']}: {ad['concepto']}",
                "objetivo": float(ad["valor"] or 0.0),
                "cubierto": 0.0,
            }
        )

    # El descuento reduce el saldo exigible empezando desde los últimos bloques
    descuento_restante = float(estructura["descuento"] or 0.0)
    for b in reversed(bloques):
        if descuento_restante <= 0:
            break
        rebaja = min(b["objetivo"], descuento_restante)
        b["objetivo"] = round(b["objetivo"] - rebaja, 2)
        descuento_restante = round(descuento_restante - rebaja, 2)

    acumulado_capital = 0.0
    total_intereses = 0.0
    total_mora = 0.0
    filas = []

    for m in movimientos:
        cap = float(
            m.base_gravable
            if m.base_gravable is not None
            else (m.valor_neto or m.valor or 0.0)
        )
        inte = float(m.valor_intereses or 0.0)
        mora = float(m.valor_mora or 0.0)

        acumulado_capital += cap
        total_intereses += inte
        total_mora += mora

        por_aplicar = cap
        etapas_tocadas = []

        for b in bloques:
            if por_aplicar <= 0:
                break
            faltante = round(b["objetivo"] - b["cubierto"], 2)
            if faltante <= 0:
                continue
            abono_bloque = min(faltante, por_aplicar)
            b["cubierto"] = round(b["cubierto"] + abono_bloque, 2)
            por_aplicar = round(por_aplicar - abono_bloque, 2)
            etapas_tocadas.append(b["titulo"])

        if por_aplicar > 0:
            etapas_tocadas.append("Excedente a favor del cliente")
        elif not etapas_tocadas:
            etapas_tocadas.append("Proyecto cubierto al 100%")

        filas.append(
            {
                "movimiento": m,
                "capital": round(cap, 2),
                "intereses": round(inte, 2),
                "mora": round(mora, 2),
                "total_movimiento": round(cap + inte + mora, 2),
                "acumulado_capital": round(acumulado_capital, 2),
                "etapa_liberada": " + ".join(dict.fromkeys(etapas_tocadas)),
            }
        )

    for b in bloques:
        b["pendiente"] = round(max(0.0, b["objetivo"] - b["cubierto"]), 2)
        b["avance_pct"] = (
            min(100.0, round((b["cubierto"] / b["objetivo"]) * 100.0, 1))
            if b["objetivo"] > 0
            else 100.0
        )

    total_cubierto = round(sum(b["cubierto"] for b in bloques), 2)
    saldo_pendiente = round(max(0.0, estructura["total_proyecto"] - total_cubierto), 2)

    return {
        "bloques": bloques,
        "filas": filas,
        "total_capital_pagado": round(acumulado_capital, 2),
        "total_intereses_pagados": round(total_intereses, 2),
        "total_mora_pagada": round(total_mora, 2),
        "total_pagos_crv": round(acumulado_capital + total_intereses + total_mora, 2),
        "total_cubierto_proyecto": total_cubierto,
        "saldo_pendiente_proyecto": saldo_pendiente,
    }


@crv_bp.route("/perfil-cliente", methods=["GET"])
def perfil_cliente_crv():
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    empresa_nombre = session.get("empresa_nombre", "CRV CONSTRUCTORA")

    cliente_id_raw = (request.args.get("cliente_id") or "").strip()
    perfil_id_raw = (request.args.get("perfil_id") or "").strip()
    buscar = (request.args.get("buscar") or "").strip()
    proyecto = (request.args.get("proyecto") or "").strip()

    clientes = (
        CRVTercero.query.filter(
            CRVTercero.empresa_id == empresa_id,
            CRVTercero.activo == True,
            CRVTercero.tipo_tercero == "CLIENTE",
        )
        .order_by(CRVTercero.razon_social.asc())
        .all()
    )

    cliente_seleccionado = None
    if cliente_id_raw.isdigit():
        cliente_seleccionado = CRVTercero.query.filter_by(
            id=int(cliente_id_raw),
            empresa_id=empresa_id,
            tipo_tercero="CLIENTE",
        ).first()
    elif buscar:
        cliente_seleccionado = (
            CRVTercero.query.filter(
                CRVTercero.empresa_id == empresa_id,
                CRVTercero.tipo_tercero == "CLIENTE",
                or_(
                    CRVTercero.razon_social.ilike(f"%{buscar}%"),
                    CRVTercero.identificacion.ilike(f"%{buscar}%"),
                ),
            )
            .order_by(CRVTercero.razon_social.asc())
            .first()
        )

    perfiles_cliente = []
    perfil_activo = None
    if cliente_seleccionado:
        perfiles_cliente = (
            CRVPerfilCliente.query.filter_by(
                empresa_id=empresa_id,
                tercero_id=cliente_seleccionado.id,
                activo=True,
            )
            .order_by(CRVPerfilCliente.id.desc())
            .all()
        )
        if perfil_id_raw.isdigit():
            perfil_activo = next(
                (p for p in perfiles_cliente if p.id == int(perfil_id_raw)),
                None,
            )
        if perfil_activo is None and perfiles_cliente:
            perfil_activo = perfiles_cliente[0]

    movimientos = []
    ns_capital = 0.0
    ns_intereses = 0.0
    ns_mora = 0.0
    saldo_pendiente = 0.0
    resumen_negocio = None
    estructura_perfil = None
    liberacion = None
    contratos_listado = []

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

        proyecto_filtro = proyecto or (
            perfil_activo.proyecto if perfil_activo and perfil_activo.proyecto else ""
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
                else (m.valor_neto or m.valor or 0.0)
            )
            inte = float(m.valor_intereses or 0.0)
            mora = float(m.valor_mora or 0.0)
            ns_capital += cap
            ns_intereses += inte
            ns_mora += mora

        if perfil_activo:
            estructura_perfil = _calcular_estructura_perfil(perfil_activo)
            liberacion = _aplicar_liberacion_cronologica(estructura_perfil, movimientos)
            saldo_pendiente = liberacion["saldo_pendiente_proyecto"]
            resumen_negocio = {
                "valor_total": estructura_perfil["total_proyecto"],
                "valor_inicial": liberacion["total_capital_pagado"],
                "saldo_credito": saldo_pendiente,
            }
        elif cliente_seleccionado:
            cxc_query = CRVCuentaCobrar.query.filter_by(
                empresa_id=empresa_id,
                cliente_id=cliente_seleccionado.id,
            )
            if proyecto_filtro:
                cxc_query = cxc_query.filter(
                    or_(
                        CRVCuentaCobrar.proyecto.ilike(f"%{proyecto_filtro}%"),
                        CRVCuentaCobrar.obra.ilike(f"%{proyecto_filtro}%"),
                        CRVCuentaCobrar.concepto.ilike(f"%{proyecto_filtro}%"),
                    )
                )
            cuentas = cxc_query.all()
            if cuentas:
                valor_total_cxc = sum(
                    float(c.valor_neto or c.valor_bruto or 0.0) for c in cuentas
                )
                saldo_pendiente = sum(
                    float(c.saldo_pendiente or 0.0) for c in cuentas
                )
                resumen_negocio = {
                    "valor_total": round(valor_total_cxc, 2),
                    "valor_inicial": round(ns_capital, 2),
                    "saldo_credito": round(saldo_pendiente, 2),
                }
    else:
        # Vista inicial sin filtros: lista todos los contratos creados en la empresa
        todos_perfiles = (
            CRVPerfilCliente.query.filter_by(
                empresa_id=empresa_id,
                activo=True,
            )
            .order_by(CRVPerfilCliente.id.desc())
            .all()
        )
        total_global_proyecto = 0.0
        total_global_adicionales = 0.0

        for p in todos_perfiles:
            est = _calcular_estructura_perfil(p)
            cond_mov = [CRVMovimiento.tercero_id == p.tercero_id]
            if p.tercero and p.tercero.identificacion:
                cond_mov.append(
                    CRVMovimiento.tercero_identificacion == p.tercero.identificacion
                )
            movs_p = (
                CRVMovimiento.query.filter(
                    CRVMovimiento.empresa_id == empresa_id,
                    CRVMovimiento.estado == "ACTIVO",
                    CRVMovimiento.tipo.in_(["INGRESO", "COBRO CUENTA POR COBRAR"]),
                    ~CRVMovimiento.origen_registro.like("CUENTA_POR_COBRAR:%"),
                    or_(*cond_mov),
                )
                .order_by(CRVMovimiento.fecha.asc(), CRVMovimiento.id.asc())
                .all()
            )
            lib = _aplicar_liberacion_cronologica(est, movs_p)
            avance_pct = (
                min(100.0, round((lib["total_cubierto_proyecto"] / est["total_proyecto"]) * 100.0, 1))
                if est["total_proyecto"] > 0
                else 100.0
            )

            total_global_proyecto += est["total_proyecto"]
            total_global_adicionales += est["total_adicionales"]
            ns_capital += lib["total_capital_pagado"]
            ns_intereses += lib["total_intereses_pagados"]
            ns_mora += lib["total_mora_pagada"]
            saldo_pendiente += lib["saldo_pendiente_proyecto"]

            contratos_listado.append(
                {
                    "perfil": p,
                    "cliente": p.tercero,
                    "estructura": est,
                    "liberacion": lib,
                    "avance_pct": avance_pct,
                }
            )

        if contratos_listado:
            resumen_negocio = {
                "valor_total": round(total_global_proyecto, 2),
                "valor_inicial": round(ns_capital, 2),
                "saldo_credito": round(saldo_pendiente, 2),
                "total_adicionales": round(total_global_adicionales, 2),
            }

    return render_template(
        "contabilidad/crv_perfil_cliente.html",
        empresa_nombre=empresa_nombre,
        clientes=clientes,
        cliente_seleccionado=cliente_seleccionado,
        perfiles_cliente=perfiles_cliente,
        perfil_activo=perfil_activo,
        estructura_perfil=estructura_perfil,
        liberacion=liberacion,
        contratos_listado=contratos_listado,
        tipos_concepto_base=TIPOS_CONCEPTO_BASE,
        buscar=buscar,
        proyecto=proyecto,
        movimientos=movimientos,
        ns_capital=round(ns_capital, 2),
        ns_intereses=round(ns_intereses, 2),
        ns_mora=round(ns_mora, 2),
        saldo_pendiente=round(saldo_pendiente, 2),
        resumen_negocio=resumen_negocio,
    )


@crv_bp.route("/perfil-cliente/guardar", methods=["POST"])
def guardar_perfil_cliente_crv():
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    tercero_id_raw = (request.form.get("tercero_id") or "").strip()
    if not tercero_id_raw.isdigit():
        flash("Debes seleccionar un cliente CRV válido.", "error")
        return redirect(url_for("crv.perfil_cliente_crv"))

    cliente = CRVTercero.query.filter_by(
        id=int(tercero_id_raw),
        empresa_id=empresa_id,
        tipo_tercero="CLIENTE",
    ).first()
    if not cliente:
        flash("El cliente seleccionado no pertenece a la empresa activa.", "error")
        return redirect(url_for("crv.perfil_cliente_crv"))

    conceptos_base_limpios = _extraer_conceptos_base_formulario(request.form)
    if not conceptos_base_limpios:
        flash("Debes agregar al menos un concepto base (ej. Valor Lote o Valor Casa) mayor a $0.", "error")
        return redirect(url_for("crv.perfil_cliente_crv", cliente_id=cliente.id))

    tramos_limpios = _extraer_tramos_formulario(request.form)
    if not tramos_limpios:
        tramos_limpios = [{"orden": 1, "concepto": "Pago único / Contado (100%)", "porcentaje": 100.0}]

    suma_pct = round(sum(t["porcentaje"] for t in tramos_limpios), 2)
    if abs(suma_pct - 100.0) > 0.05:
        flash(f"La suma de los porcentajes de los tramos debe ser 100% (actualmente suma {suma_pct:g}%).", "error")
        return redirect(url_for("crv.perfil_cliente_crv", cliente_id=cliente.id))

    total_base = round(sum(c["valor"] for c in conceptos_base_limpios), 2)
    etiqueta_resumen = " + ".join(c["concepto"] for c in conceptos_base_limpios)[:145]
    proyecto = (request.form.get("proyecto") or "").strip() or None
    descuento = max(0.0, _parse_float(request.form.get("descuento"), 0.0))
    observaciones = (request.form.get("observaciones") or "").strip() or None
    adicionales_limpios = _extraer_adicionales_formulario(request.form)

    modo_tramos = (request.form.get("modo_tramos") or "TODOS").strip()
    tramo_idx_raw = (request.form.get("tramo_concepto_index") or "").strip()

    if modo_tramos == "SOLO_UNO" and tramo_idx_raw.isdigit() and int(tramo_idx_raw) < len(conceptos_base_limpios):
        idx_objetivo = int(tramo_idx_raw)
        tipo_concepto_guardar = f"SOLO_CONCEPTO:{idx_objetivo}"
        base_calculo_tramos = conceptos_base_limpios[idx_objetivo]["valor"]
    else:
        tipo_concepto_guardar = "MULTIPLE" if len(conceptos_base_limpios) > 1 else "VALOR_LOTE"
        base_calculo_tramos = total_base

    pct1 = tramos_limpios[0]["porcentaje"]
    pct2 = tramos_limpios[1]["porcentaje"] if len(tramos_limpios) > 1 else 0.0

    perfil = CRVPerfilCliente(
        empresa_id=empresa_id,
        tercero_id=cliente.id,
        proyecto=proyecto,
        tipo_concepto_base=tipo_concepto_guardar,
        concepto_base_label=etiqueta_resumen,
        valor_base=total_base,
        porcentaje_tramo_1=pct1,
        porcentaje_tramo_2=pct2,
        descuento=descuento,
        observaciones=observaciones,
        activo=True,
        usuario_registro=session.get("usuario_nombre") or session.get("usuario"),
    )

    for cb in conceptos_base_limpios:
        perfil.items.append(
            CRVPerfilClienteItem(
                categoria="BASE",
                orden=cb["orden"],
                concepto=cb["concepto"],
                porcentaje=0.0,
                valor=cb["valor"],
            )
        )

    for tr in tramos_limpios:
        monto_tramo = round(base_calculo_tramos * (tr["porcentaje"] / 100.0), 2)
        perfil.items.append(
            CRVPerfilClienteItem(
                categoria="TRAMO",
                orden=tr["orden"],
                concepto=tr["concepto"],
                porcentaje=tr["porcentaje"],
                valor=monto_tramo,
            )
        )

    for ad in adicionales_limpios:
        perfil.adicionales.append(
            CRVPerfilClienteAdicional(
                orden=ad["orden"],
                concepto=ad["concepto"],
                valor=ad["valor"],
            )
        )

    db.session.add(perfil)
    db.session.commit()

    flash("Contrato de Perfil Cliente CRV creado correctamente.", "success")
    return redirect(
        url_for("crv.perfil_cliente_crv", cliente_id=cliente.id, perfil_id=perfil.id)
    )


@crv_bp.route("/perfil-cliente/<int:perfil_id>/editar", methods=["POST"])
def editar_perfil_cliente_crv(perfil_id):
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    perfil = CRVPerfilCliente.query.filter_by(
        id=perfil_id,
        empresa_id=empresa_id,
    ).first_or_404()

    conceptos_base_limpios = _extraer_conceptos_base_formulario(request.form)
    if not conceptos_base_limpios:
        flash("Debes mantener al menos un concepto base mayor a $0.", "error")
        return redirect(
            url_for("crv.perfil_cliente_crv", cliente_id=perfil.tercero_id, perfil_id=perfil.id)
        )

    tramos_limpios = _extraer_tramos_formulario(request.form)
    if not tramos_limpios:
        tramos_limpios = [{"orden": 1, "concepto": "Pago único / Contado (100%)", "porcentaje": 100.0}]

    suma_pct = round(sum(t["porcentaje"] for t in tramos_limpios), 2)
    if abs(suma_pct - 100.0) > 0.05:
        flash(f"La suma de los porcentajes de los tramos debe ser 100% (actualmente suma {suma_pct:g}%).", "error")
        return redirect(
            url_for("crv.perfil_cliente_crv", cliente_id=perfil.tercero_id, perfil_id=perfil.id)
        )

    total_base = round(sum(c["valor"] for c in conceptos_base_limpios), 2)
    etiqueta_resumen = " + ".join(c["concepto"] for c in conceptos_base_limpios)[:145]

    modo_tramos = (request.form.get("modo_tramos") or "TODOS").strip()
    tramo_idx_raw = (request.form.get("tramo_concepto_index") or "").strip()

    if modo_tramos == "SOLO_UNO" and tramo_idx_raw.isdigit() and int(tramo_idx_raw) < len(conceptos_base_limpios):
        idx_objetivo = int(tramo_idx_raw)
        tipo_concepto_guardar = f"SOLO_CONCEPTO:{idx_objetivo}"
        base_calculo_tramos = conceptos_base_limpios[idx_objetivo]["valor"]
    else:
        tipo_concepto_guardar = "MULTIPLE" if len(conceptos_base_limpios) > 1 else "VALOR_LOTE"
        base_calculo_tramos = total_base

    perfil.proyecto = (request.form.get("proyecto") or "").strip() or None
    perfil.tipo_concepto_base = tipo_concepto_guardar
    perfil.concepto_base_label = etiqueta_resumen
    perfil.valor_base = total_base
    perfil.porcentaje_tramo_1 = tramos_limpios[0]["porcentaje"]
    perfil.porcentaje_tramo_2 = tramos_limpios[1]["porcentaje"] if len(tramos_limpios) > 1 else 0.0
    perfil.descuento = max(0.0, _parse_float(request.form.get("descuento"), 0.0))
    perfil.observaciones = (request.form.get("observaciones") or "").strip() or None
    perfil.fecha_actualizacion = datetime.utcnow()

    perfil.items.clear()
    for cb in conceptos_base_limpios:
        perfil.items.append(
            CRVPerfilClienteItem(
                categoria="BASE",
                orden=cb["orden"],
                concepto=cb["concepto"],
                porcentaje=0.0,
                valor=cb["valor"],
            )
        )

    for tr in tramos_limpios:
        monto_tramo = round(base_calculo_tramos * (tr["porcentaje"] / 100.0), 2)
        perfil.items.append(
            CRVPerfilClienteItem(
                categoria="TRAMO",
                orden=tr["orden"],
                concepto=tr["concepto"],
                porcentaje=tr["porcentaje"],
                valor=monto_tramo,
            )
        )

    perfil.adicionales.clear()
    for ad in _extraer_adicionales_formulario(request.form):
        perfil.adicionales.append(
            CRVPerfilClienteAdicional(
                orden=ad["orden"],
                concepto=ad["concepto"],
                valor=ad["valor"],
            )
        )

    db.session.commit()
    flash("Contrato actualizado correctamente.", "success")
    return redirect(
        url_for("crv.perfil_cliente_crv", cliente_id=perfil.tercero_id, perfil_id=perfil.id)
    )


@crv_bp.route("/perfil-cliente/<int:perfil_id>/eliminar", methods=["POST"])
def eliminar_perfil_cliente_crv(perfil_id):
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    perfil = CRVPerfilCliente.query.filter_by(
        id=perfil_id,
        empresa_id=empresa_id,
    ).first_or_404()

    cliente_id = perfil.tercero_id
    db.session.delete(perfil)
    db.session.commit()

    flash("Contrato del cliente CRV eliminado correctamente.", "success")
    return redirect(url_for("crv.perfil_cliente_crv", cliente_id=cliente_id))