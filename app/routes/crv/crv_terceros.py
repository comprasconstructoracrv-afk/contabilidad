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

import pandas as pd
from datetime import datetime

@crv_bp.route("/terceros/importar-excel", methods=["POST"])
def importar_terceros_excel():
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    archivo = request.files.get("archivo_excel")

    if not empresa_id:
        flash("Debes tener una empresa activa en la sesión.", "error")
        return redirect("/crv/terceros")

    if not archivo or not archivo.filename.endswith((".xlsx", ".xls")):
        flash("Por favor selecciona un archivo de Excel válido (.xlsx o .xls).", "error")
        return redirect("/crv/terceros")

    # Función auxiliar para limpiar celdas (afuera del bucle)
    def _clean(val, default=""):
        if pd.isna(val) or val is None:
            return default
        text = str(val).strip()
        return text if text.lower() != "nan" else default

    # Mapeo flexible para tipos de tercero
    mapa_tipos_tercero = {
        "CLIENTE": "CLIENTE",
        "CLIENTES": "CLIENTE",
        "PROVEEDOR": "PROVEEDOR",
        "PROVEEDORES": "PROVEEDOR",
        "EMPLEADO": "EMPLEADO",
        "EMPLEADOS": "EMPLEADO",
        "CONTRATISTA": "CONTRATISTA",
        "CONTRATISTAS": "CONTRATISTA"
    }

    try:
        # Cargar Excel forzando string para no perder ceros a la izquierda
        df = pd.read_excel(archivo, dtype=str)

        # Normalizar encabezados (quitar espacios invisibles y pasar a mayúsculas)
        df.columns = [str(col).strip().upper() for col in df.columns]

        # Validar columnas mínimas indispensables
        columnas_obligatorias = {"IDENTIFICACION", "RAZON_SOCIAL"}
        if not columnas_obligatorias.issubset(df.columns):
            flash("El archivo Excel debe contener al menos las columnas IDENTIFICACION y RAZON_SOCIAL.", "error")
            return redirect("/crv/terceros")

        creados = 0
        actualizados = 0
        omitidos = 0

        for _, fila in df.iterrows():
            identificacion = _clean(fila.get("IDENTIFICACION"))
            razon_social = _clean(fila.get("RAZON_SOCIAL"))

            # Omitir filas sin datos clave
            if not identificacion or not razon_social:
                omitidos += 1
                continue

            # Limpieza y normalización de tipo tercero y tipo documento
            tipo_raw = _clean(fila.get("TIPO_TERCERO"), "CLIENTE").upper()
            tipo_tercero = mapa_tipos_tercero.get(tipo_raw, "CLIENTE")
            
            tipo_doc_raw = _clean(fila.get("TIPO_DOCUMENTO"), "CC").upper()
            tipo_documento = tipo_doc_raw if tipo_doc_raw else ("CC" if tipo_tercero == "EMPLEADO" else "NIT")

            nombre_comercial = _clean(fila.get("NOMBRE_COMERCIAL"))
            direccion = _clean(fila.get("DIRECCION"))
            ciudad = _clean(fila.get("CIUDAD"))
            departamento = _clean(fila.get("DEPARTAMENTO"))
            telefono = _clean(fila.get("TELEFONO"))
            celular = _clean(fila.get("CELULAR"))
            email = _clean(fila.get("EMAIL"))
            contacto = _clean(fila.get("CONTACTO"))
            banco = _clean(fila.get("BANCO"))
            tipo_cuenta = _clean(fila.get("TIPO_CUENTA"))
            numero_cuenta = _clean(fila.get("NUMERO_CUENTA"))
            titular_cuenta = _clean(fila.get("TITULAR_CUENTA"))
            observaciones = _clean(fila.get("OBSERVACIONES"))

            # Verificar si ya existe el tercero por identificación y empresa
            tercero_existente = CRVTercero.query.filter_by(
                empresa_id=empresa_id,
                identificacion=identificacion
            ).first()

            if tercero_existente:
                tercero_existente.tipo_tercero = tipo_tercero
                tercero_existente.tipo_documento = tipo_documento
                tercero_existente.razon_social = razon_social
                tercero_existente.nombre_comercial = nombre_comercial
                tercero_existente.direccion = direccion
                tercero_existente.ciudad = ciudad
                tercero_existente.departamento = departamento
                tercero_existente.telefono = telefono
                tercero_existente.celular = celular
                tercero_existente.email = email
                tercero_existente.contacto = contacto
                tercero_existente.banco = banco
                tercero_existente.tipo_cuenta = tipo_cuenta
                tercero_existente.numero_cuenta = numero_cuenta
                tercero_existente.titular_cuenta = titular_cuenta
                tercero_existente.observaciones = observaciones
                tercero_existente.fecha_actualizacion = datetime.utcnow()
                actualizados += 1
            else:
                nuevo_tercero = CRVTercero(
                    empresa_id=empresa_id,
                    tipo_tercero=tipo_tercero,
                    tipo_documento=tipo_documento,
                    identificacion=identificacion,
                    razon_social=razon_social,
                    nombre_comercial=nombre_comercial,
                    direccion=direccion,
                    ciudad=ciudad,
                    departamento=departamento,
                    telefono=telefono,
                    celular=celular,
                    email=email,
                    contacto=contacto,
                    banco=banco,
                    tipo_cuenta=tipo_cuenta,
                    numero_cuenta=numero_cuenta,
                    titular_cuenta=titular_cuenta,
                    observaciones=observaciones,
                    activo=True,
                    fecha_creacion=datetime.utcnow(),
                    fecha_actualizacion=datetime.utcnow()
                )
                db.session.add(nuevo_tercero)
                creados += 1

        db.session.commit()

        msg = f"Carga completada exitosamente: {creados} terceros creados, {actualizados} actualizados."
        if omitidos > 0:
            msg += f" ({omitidos} filas omitidas por no tener identificación o razón social)."
        flash(msg, "success")

    except Exception as e:
        db.session.rollback()
        print(f"[ERROR EN RAILWAY IMPORTACIÓN TERCEROS]: {str(e)}")
        flash(f"Ocurrió un error al procesar el archivo Excel: {str(e)}", "error")

    return redirect("/crv/terceros")

@crv_bp.route("/terceros/eliminar/<int:tercero_id>", methods=["POST"])
def eliminar_tercero(tercero_id):
    bloqueo = proteger_crv()
    if bloqueo:
        return bloqueo

    empresa_id = session.get("empresa_id")
    tercero = CRVTercero.query.get_or_404(tercero_id)

    if tercero.empresa_id != empresa_id:
        flash("No tienes permiso para realizar esta acción.", "error")
        return redirect("/crv/terceros")

    # Verificar si el tercero ya tiene movimientos contables asociados
    if tercero.movimientos and len(tercero.movimientos) > 0:
        flash(
            "No se puede eliminar el tercero porque ya posee movimientos contables asociados. Te sugerimos cambiar su estado a Inactivo.",
            "error"
        )
        return redirect("/crv/terceros")

    try:
        db.session.delete(tercero)
        db.session.commit()
        flash("Tercero eliminado permanentemente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al eliminar el tercero: {str(e)}", "error")

    return redirect("/crv/terceros")

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

__all__ = ['terceros', 'cambiar_estado_tercero', 'editar_tercero', 'importar_terceros_excel', 'eliminar_tercero']
