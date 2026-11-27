"""CRV Perfil Cliente routes and dynamic contract/release logic."""

from flask import url_for
from sqlalchemy import or_

from app.models.crv_perfil_cliente import (
    CRVPerfilCliente,
    CRVPerfilClienteAdicional,
    CRVPerfilClienteItem,
)
from .crv_core import (
    CRVCuentaCobrar,
    CRVMovimiento,
    CRVTercero,
    convertir_numero,
    convertir_porcentaje,
    crv_bp,
    db,
    flash,
    proteger_crv,
    redirect,
    render_template,
    request,
    session,
)

TIPOS_CONCEPTO_BASE = {
    "VALOR_LOTE": "Valor Lote",
    "VALOR_CASA": "Valor Casa",
    "VALOR_CONSTRUCCION": "Valor Construcción",
    "VALOR_LOTE_CONSTRUCCION": "Valor Lote - Construcción",
    "VALOR_LOTE_CASA": "Valor Lote - Casa",
}

def _calcular_estructura_perfil(perfil):
    items_base = [
        it for it in perfil.items if (it.categoria or "").upper() == "BASE"
    ]
    items_tramo = [
        it for it in perfil.items if (it.categoria or "").upper().startswith("TRAMO")
    ]

    if items_base:
        conceptos_base = [
            {
                "id": it.id,
                "orden": it.orden,
                "concepto": it.concepto,
                "valor": round(float(it.valor or 0.0), 2),
                "tramos": [],
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
                "tramos": [],
            }
        ]

    total_base = round(sum(c["valor"] for c in conceptos_base), 2)
    mapa_base_por_orden = {c["orden"]: c for c in conceptos_base}

    modo_raw = (perfil.tipo_concepto_base or "").strip()
    aplica_a_indice_legacy = None
    if modo_raw.startswith("SOLO_CONCEPTO:"):
        idx_str = modo_raw.split(":", 1)[1].strip()
        if idx_str.isdigit() and 0 <= int(idx_str) < len(conceptos_base):
            aplica_a_indice_legacy = int(idx_str)

    tramos_globales = []

    if items_tramo:
        for it in items_tramo:
            cat_upper = (it.categoria or "").upper().strip()
            pct = float(it.porcentaje or 0.0)

            # Tramo individual de un concepto: TRAMO:<orden_base>
            if ":" in cat_upper and cat_upper.split(":", 1)[1].isdigit():
                orden_padre = int(cat_upper.split(":", 1)[1])
                cb_padre = mapa_base_por_orden.get(orden_padre)
                if cb_padre:
                    monto = (
                        round(cb_padre["valor"] * (pct / 100.0), 2)
                        if pct > 0
                        else round(float(it.valor or 0.0), 2)
                    )
                    cb_padre["tramos"].append(
                        {
                            "id": it.id,
                            "orden": it.orden,
                            "concepto": it.concepto,
                            "porcentaje": pct,
                            "monto": monto,
                        }
                    )
                    continue

            # Tramo global sobre subtotal (o sobre índice legacy)
            base_ref = (
                conceptos_base[aplica_a_indice_legacy]["valor"]
                if aplica_a_indice_legacy is not None
                else total_base
            )
            monto = (
                round(base_ref * (pct / 100.0), 2)
                if pct > 0
                else round(float(it.valor or 0.0), 2)
            )
            tramo_obj = {
                "id": it.id,
                "orden": it.orden,
                "concepto": it.concepto,
                "porcentaje": pct,
                "monto": monto,
            }
            if aplica_a_indice_legacy is not None:
                conceptos_base[aplica_a_indice_legacy]["tramos"].append(tramo_obj)
            else:
                tramos_globales.append(tramo_obj)
    else:
        pct1 = float(perfil.porcentaje_tramo_1 or 0.0)
        pct2 = float(perfil.porcentaje_tramo_2 or 0.0)
        tramos_globales.append(
            {
                "id": None,
                "orden": 1,
                "concepto": f"Tramo 1 ({pct1:g}%)",
                "porcentaje": pct1,
                "monto": round(total_base * (pct1 / 100.0), 2),
            }
        )
        if pct2 > 0:
            tramos_globales.append(
                {
                    "id": None,
                    "orden": 2,
                    "concepto": f"Tramo 2 ({pct2:g}%)",
                    "porcentaje": pct2,
                    "monto": round(total_base * (pct2 / 100.0), 2),
                }
            )

    todos_tramos = []
    for cb in conceptos_base:
        todos_tramos.extend(cb["tramos"])
    todos_tramos.extend(tramos_globales)

    tiene_tramos_por_concepto = any(len(cb["tramos"]) > 0 for cb in conceptos_base)
    modo_esquema = "POR_CONCEPTO" if tiene_tramos_por_concepto else "GLOBAL"

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
    total_proyecto = round(max(0.0, total_base + total_adicionales - descuento), 2)

    return {
        "conceptos_base": conceptos_base,
        "total_base": total_base,
        "modo_esquema": modo_esquema,
        "tiene_tramos_por_concepto": tiene_tramos_por_concepto,
        "tramos": todos_tramos,
        "tramos_globales": tramos_globales,
        "adicionales": adicionales,
        "total_adicionales": total_adicionales,
        "descuento": descuento,
        "total_proyecto": total_proyecto,
    }


def _aplicar_liberacion_cronologica(estructura, movimientos):
    bloques = []

    if estructura.get("modo_esquema") == "POR_CONCEPTO":
        # Respeta el orden exacto de cada concepto base y sus propios tramos (ej. Lote 70/30, Casa 50/50, 3ro directo)
        for cb in estructura["conceptos_base"]:
            if cb["tramos"]:
                for t_idx, tr in enumerate(cb["tramos"], start=1):
                    bloques.append(
                        {
                            "tipo": "TRAMO",
                            "orden": t_idx,
                            "titulo": f"{cb['concepto']} - {tr['concepto']}",
                            "objetivo": float(tr["monto"] or 0.0),
                            "cubierto": 0.0,
                        }
                    )
            else:
                bloques.append(
                    {
                        "tipo": "CONCEPTO_DIRECTO",
                        "orden": cb["orden"],
                        "titulo": cb["concepto"],
                        "objetivo": float(cb["valor"] or 0.0),
                        "cubierto": 0.0,
                    }
                )
    else:
        # Modo GLOBAL: aplica los porcentajes (ej. 70/30) sobre el subtotal de todos los conceptos base
        for t_idx, tr in enumerate(estructura.get("tramos_globales", []), start=1):
            bloques.append(
                {
                    "tipo": "TRAMO",
                    "orden": t_idx,
                    "titulo": tr["concepto"],
                    "objetivo": float(tr["monto"] or 0.0),
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

    # Descuento se rebaja desde los últimos bloques
    descuento_restante = float(estructura["descuento"] or 0.0)
    for b in reversed(bloques):
        if descuento_restante <= 0:
            break
        rebaja = min(b["objetivo"], descuento_restante)
        b["objetivo"] = round(b["objetivo"] - rebaja, 2)
        descuento_restante = round(descuento_restante - rebaja, 2)

    suma_bloques = round(sum(b["objetivo"] for b in bloques), 2)
    resto_objetivo = max(0.0, round(float(estructura["total_proyecto"]) - suma_bloques, 2))
    if resto_objetivo > 0:
        bloques.append(
            {
                "tipo": "RESTO",
                "orden": len(bloques) + 1,
                "titulo": "Saldo restante del proyecto",
                "objetivo": resto_objetivo,
                "cubierto": 0.0,
            }
        )

    acumulado_capital = 0.0
    acumulado_intereses = 0.0
    acumulado_mora = 0.0
    filas_liberadas = []

    for m in movimientos:
        cap = max(
            0.0,
            float(
                m.base_gravable
                if m.base_gravable is not None
                else (m.valor_neto or m.valor or 0.0)
            ),
        )
        inte = max(0.0, float(m.valor_intereses or 0.0))
        mora = max(0.0, float(m.valor_mora or 0.0))
        total_pago = round(cap + inte + mora, 2)

        disponible = cap
        etapas_tocadas = []

        for b in bloques:
            if disponible <= 0:
                break
            faltante = max(0.0, round(b["objetivo"] - b["cubierto"], 2))
            if faltante > 0:
                asignado = min(disponible, faltante)
                b["cubierto"] = round(b["cubierto"] + asignado, 2)
                disponible = round(disponible - asignado, 2)
                if asignado > 0:
                    etapas_tocadas.append(b["titulo"])

        acumulado_capital = round(acumulado_capital + cap, 2)
        acumulado_intereses = round(acumulado_intereses + inte, 2)
        acumulado_mora = round(acumulado_mora + mora, 2)

        etapa_liberada = (
            " + ".join(dict.fromkeys(etapas_tocadas))
            if etapas_tocadas
            else "Cubierto / Excedente"
        )

        filas_liberadas.append(
            {
                "movimiento": m,
                "capital": round(cap, 2),
                "intereses": round(inte, 2),
                "mora": round(mora, 2),
                "total_pago": total_pago,
                "excedente": max(0.0, disponible),
                "acumulado_capital": acumulado_capital,
                "etapa_liberada": etapa_liberada,
            }
        )

    for b in bloques:
        b["pendiente"] = max(0.0, round(b["objetivo"] - b["cubierto"], 2))
        b["avance_pct"] = (
            min(100.0, round((b["cubierto"] / b["objetivo"]) * 100.0, 1))
            if b["objetivo"] > 0
            else 100.0
        )

    total_cubierto_proyecto = min(
        float(estructura["total_proyecto"]),
        round(sum(b["cubierto"] for b in bloques), 2),
    )
    saldo_pendiente_proyecto = max(
        0.0,
        round(float(estructura["total_proyecto"]) - total_cubierto_proyecto, 2),
    )

    return {
        "filas": filas_liberadas,
        "bloques": bloques,
        "total_capital_pagado": acumulado_capital,
        "total_intereses_pagados": acumulado_intereses,
        "total_mora_pagada": acumulado_mora,
        "total_pagos_crv": round(
            acumulado_capital + acumulado_intereses + acumulado_mora, 2
        ),
        "total_cubierto_proyecto": total_cubierto_proyecto,
        "saldo_pendiente_proyecto": saldo_pendiente_proyecto,
    }


def _extraer_tramos_globales_formulario(form):
    nombres = form.getlist("global_tramo_concepto[]")
    porcentajes = form.getlist("global_tramo_porcentaje[]")
    items = []
    orden = 1
    for i in range(max(len(nombres), len(porcentajes))):
        nom = (nombres[i] if i < len(nombres) else "").strip()
        pct = max(
            0.0,
            convertir_porcentaje(porcentajes[i] if i < len(porcentajes) else 0, default=0.0),
        )
        if nom or pct > 0:
            items.append(
                {
                    "orden": orden,
                    "concepto": nom or (f"Pago único ({pct:g}%)" if orden == 1 and len(porcentajes) == 1 else f"Tramo {orden} ({pct:g}%)"),
                    "porcentaje": round(pct, 2),
                }
            )
            orden += 1
    if not items:
        items.append(
            {
                "orden": 1,
                "concepto": "Pago único / Contado (100%)",
                "porcentaje": 100.0,
            }
        )
    return items


def _extraer_conceptos_y_tramos_formulario(form):
    conceptos = form.getlist("base_concepto[]") or form.getlist("base_concepto")
    valores = form.getlist("base_valor[]") or form.getlist("base_valor")
    grupos_id = form.getlist("base_grupo_id[]")

    tramo_grupos = form.getlist("tramo_grupo_id[]")
    tramo_nombres = form.getlist("tramo_concepto[]")
    tramo_porcentajes = form.getlist("tramo_porcentaje[]")

    tramos_por_grupo = {}
    for i in range(max(len(tramo_nombres), len(tramo_porcentajes))):
        gid = (tramo_grupos[i] if i < len(tramo_grupos) else "").strip()
        nom = (tramo_nombres[i] if i < len(tramo_nombres) else "").strip()
        pct = max(
            0.0,
            convertir_porcentaje(
                tramo_porcentajes[i] if i < len(tramo_porcentajes) else 0,
                default=0.0,
            ),
        )
        if pct > 0:
            tramos_por_grupo.setdefault(gid, []).append(
                {
                    "concepto": nom,
                    "porcentaje": round(pct, 2),
                }
            )

    items_base = []
    orden_base = 1
    for i in range(max(len(conceptos), len(valores))):
        conc = (conceptos[i] if i < len(conceptos) else "").strip()
        val = max(
            0.0,
            convertir_numero(valores[i] if i < len(valores) else 0, default=0.0),
        )
        gid = (grupos_id[i] if i < len(grupos_id) else str(i)).strip()

        if conc or val > 0:
            tramos_de_este = tramos_por_grupo.get(gid, [])
            tramos_limpios = []
            for idx_t, tr in enumerate(tramos_de_este, start=1):
                nom_tr = tr["concepto"] or (
                    f"Pago único ({tr['porcentaje']:g}%)"
                    if len(tramos_de_este) == 1
                    else f"Tramo {idx_t} ({tr['porcentaje']:g}%)"
                )
                tramos_limpios.append(
                    {
                        "orden": idx_t,
                        "concepto": nom_tr,
                        "porcentaje": tr["porcentaje"],
                    }
                )

            items_base.append(
                {
                    "orden": orden_base,
                    "concepto": conc or f"Concepto base #{orden_base}",
                    "valor": round(val, 2),
                    "tramos": tramos_limpios,
                }
            )
            orden_base += 1

    return items_base

def _guardar_o_actualizar_perfil(empresa_id, form, perfil=None):
    tercero_id_raw = (form.get("tercero_id") or form.get("cliente_id") or "").strip()
    if not tercero_id_raw.isdigit():
        raise ValueError("Debes seleccionar un cliente CRV válido.")

    tercero = CRVTercero.query.filter_by(
        id=int(tercero_id_raw),
        empresa_id=empresa_id,
    ).first()
    if not tercero:
        raise ValueError("El tercero seleccionado no existe en la empresa activa.")

    if (tercero.tipo_tercero or "").strip().upper() != "CLIENTE":
        raise ValueError("El Perfil Cliente CRV aplica únicamente para terceros de tipo CLIENTE.")

    modo_esquema = (form.get("modo_esquema_tramos") or "GLOBAL").strip().upper()
    conceptos_base = _extraer_conceptos_y_tramos_formulario(form)
    if not conceptos_base:
        raise ValueError("Debes ingresar al menos un concepto principal (Ej. Valor Lote o Valor Casa).")

    tramos_globales = []
    if modo_esquema == "POR_CONCEPTO":
        for cb in conceptos_base:
            if cb["tramos"]:
                suma_pct = round(sum(t["porcentaje"] for t in cb["tramos"]), 2)
                if abs(suma_pct - 100.0) > 0.05:
                    raise ValueError(
                        f"Los tramos de '{cb['concepto']}' deben sumar 100% (actualmente suman {suma_pct:g}%)."
                    )
    else:
        tramos_globales = _extraer_tramos_globales_formulario(form)
        suma_global = round(sum(t["porcentaje"] for t in tramos_globales), 2)
        if abs(suma_global - 100.0) > 0.05:
            raise ValueError(
                f"Los tramos porcentuales globales deben sumar 100% (actualmente suman {suma_global:g}%)."
            )

    adicionales_data = _extraer_adicionales_formulario(form)
    descuento = max(0.0, convertir_numero(form.get("descuento"), default=0.0))
    proyecto = (form.get("proyecto") or "").strip()
    observaciones = (form.get("observaciones") or "").strip()
    total_base = round(sum(c["valor"] for c in conceptos_base), 2)

    if perfil is None:
        perfil = CRVPerfilCliente(
            empresa_id=empresa_id,
            usuario_registro=str(session.get("usuario", "")),
        )
        db.session.add(perfil)

    ref_tramos = (
        tramos_globales
        if modo_esquema == "GLOBAL"
        else next((c["tramos"] for c in conceptos_base if c["tramos"]), [])
    )

    perfil.tercero_id = tercero.id
    perfil.proyecto = proyecto
    perfil.tipo_concepto_base = (
        "MULTITRAMO_POR_CONCEPTO"
        if modo_esquema == "POR_CONCEPTO"
        else ("MULTIPLE" if len(conceptos_base) > 1 else "VALOR_LOTE")
    )
    perfil.concepto_base_label = " + ".join(c["concepto"] for c in conceptos_base)[:150]
    perfil.valor_base = total_base
    perfil.porcentaje_tramo_1 = ref_tramos[0]["porcentaje"] if len(ref_tramos) >= 1 else 100.0
    perfil.porcentaje_tramo_2 = ref_tramos[1]["porcentaje"] if len(ref_tramos) >= 2 else 0.0
    perfil.descuento = round(descuento, 2)
    perfil.observaciones = observaciones
    perfil.activo = True

    perfil.items.clear()
    for cb in conceptos_base:
        perfil.items.append(
            CRVPerfilClienteItem(
                categoria="BASE",
                orden=cb["orden"],
                concepto=cb["concepto"],
                porcentaje=0.0,
                valor=cb["valor"],
            )
        )
        if modo_esquema == "POR_CONCEPTO":
            for tr in cb["tramos"]:
                perfil.items.append(
                    CRVPerfilClienteItem(
                        categoria=f"TRAMO:{cb['orden']}",
                        orden=tr["orden"],
                        concepto=tr["concepto"],
                        porcentaje=tr["porcentaje"],
                        valor=round(cb["valor"] * (tr["porcentaje"] / 100.0), 2),
                    )
                )

    if modo_esquema == "GLOBAL":
        for tr in tramos_globales:
            perfil.items.append(
                CRVPerfilClienteItem(
                    categoria="TRAMO",
                    orden=tr["orden"],
                    concepto=tr["concepto"],
                    porcentaje=tr["porcentaje"],
                    valor=round(total_base * (tr["porcentaje"] / 100.0), 2),
                )
            )

    perfil.adicionales.clear()
    for ad in adicionales_data:
        perfil.adicionales.append(
            CRVPerfilClienteAdicional(
                orden=ad["orden"],
                concepto=ad["concepto"],
                valor=ad["valor"],
            )
        )

    db.session.commit()
    return perfil


def _extraer_tramos_formulario(form):
    nombres = form.getlist("tramo_concepto[]") or form.getlist("tramo_concepto")
    porcentajes = form.getlist("tramo_porcentaje[]") or form.getlist("tramo_porcentaje")
    items = []
    orden = 1
    for i in range(max(len(nombres), len(porcentajes))):
        nom = (nombres[i] if i < len(nombres) else "").strip()
        pct = max(
            0.0,
            convertir_porcentaje(porcentajes[i] if i < len(porcentajes) else 0, default=0.0),
        )
        if nom or pct > 0:
            items.append(
                {
                    "orden": orden,
                    "concepto": nom or (f"Pago único ({pct:g}%)" if orden == 1 and len(porcentajes) == 1 else f"Tramo {orden} ({pct:g}%)"),
                    "porcentaje": round(pct, 2),
                }
            )
            orden += 1
    if not items:
        items.append(
            {
                "orden": 1,
                "concepto": "Pago único / Contado (100%)",
                "porcentaje": 100.0,
            }
        )
    return items


def _extraer_adicionales_formulario(form):
    conceptos = form.getlist("adicional_concepto[]") or form.getlist("adicional_concepto")
    valores = form.getlist("adicional_valor[]") or form.getlist("adicional_valor")
    items = []
    orden = 1
    for i in range(max(len(conceptos), len(valores))):
        conc = (conceptos[i] if i < len(conceptos) else "").strip()
        val = max(0.0, convertir_numero(valores[i] if i < len(valores) else 0, default=0.0))
        if conc or val > 0:
            items.append(
                {
                    "orden": orden,
                    "concepto": conc or f"Adicional #{orden}",
                    "valor": round(val, 2),
                }
            )
            orden += 1
    return items

@crv_bp.route("/perfil-cliente/guardar", methods=["POST"])
def guardar_perfil_cliente_crv():
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    try:
        perfil = _guardar_o_actualizar_perfil(empresa_id, request.form, perfil=None)
        flash("Contrato del cliente CRV guardado correctamente.", "success")
        return redirect(
            url_for("crv.perfil_cliente_crv", cliente_id=perfil.tercero_id, perfil_id=perfil.id)
        )
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(url_for("crv.perfil_cliente_crv"))


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

    try:
        _guardar_o_actualizar_perfil(empresa_id, request.form, perfil=perfil)
        flash("Contrato del cliente CRV actualizado y recalculado.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")

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