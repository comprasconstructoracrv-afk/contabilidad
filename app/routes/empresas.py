from flask import Blueprint, render_template, request, redirect, session
from app.extensions import db
from app.models.empresa import Empresa
from app.models.movimiento import Movimiento
from app.models.venta_ecobike import VentaEcobike
from app.models.sede import Sede


empresas_bp = Blueprint(
    "empresas_bp",
    __name__
)


# ============================================================
# RUTA PRINCIPAL SEGÚN EMPRESA
# ============================================================

def obtener_ruta_empresa(empresa):
    """
    Devuelve el dashboard correspondiente a la empresa
    seleccionada.

    IMPORTANTE:
    Cada empresa conserva sus procesos, datos, diseños,
    NIT, logo y funcionalidades por separado.
    """

    nombre = str(
        empresa.nombre or ""
    ).strip().upper()

    # --------------------------------------------------------
    # CRV CONSTRUCTORA
    # --------------------------------------------------------

    if (
        "CRV" in nombre
        and (
            "CONSTRUCTORA" in nombre
            or "CONSTRUCCIONES" in nombre
            or "URBANIZACIONES" in nombre
        )
    ):
        return "/crv/dashboard"

    # --------------------------------------------------------
    # HOTEL SKY VIEW
    # --------------------------------------------------------

    if (
        "HOTEL" in nombre
        and "SKY" in nombre
    ):
        return "/hotel-sky-view/dashboard"

    # --------------------------------------------------------
    # ECOBIKE
    # --------------------------------------------------------

    if "ECOBIKE" in nombre:
        return "/dashboard"

    # --------------------------------------------------------
    # COMERCIALIZADORA
    # --------------------------------------------------------

    if "COMERCIALIZADORA" in nombre:
        return "/dashboard"

    # --------------------------------------------------------
    # FINANCIERA
    # --------------------------------------------------------

    if (
        "FINANCIERA" in nombre
        or "CREDITO" in nombre
        or "CRÉDITO" in nombre
    ):
        return "/dashboard"

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    return "/dashboard"


# ============================================================
# RESUMEN GENERAL EMPRESA
# ============================================================

def resumen_empresa(
    empresa,
    mes=""
):
    ingresos = 0
    gastos = 0

    query_mov = Movimiento.query.filter_by(
        empresa_id=empresa.id
    )

    if mes:

        try:

            anio, numero_mes = mes.split("-")

            anio = int(anio)
            numero_mes = int(numero_mes)

            query_mov = query_mov.filter(
                db.extract(
                    "year",
                    Movimiento.fecha
                ) == anio,

                db.extract(
                    "month",
                    Movimiento.fecha
                ) == numero_mes
            )

        except ValueError:
            pass

    movimientos = query_mov.all()

    for mov in movimientos:

        tipo = str(
            mov.tipo or ""
        ).strip().upper()

        valor = float(
            mov.valor or 0
        )

        if tipo == "INGRESO":

            ingresos += valor

        elif tipo == "GASTO":

            gastos += valor

    utilidad = (
        ingresos
        - gastos
    )

    return {
        "empresa": empresa.nombre,
        "ingresos": ingresos,
        "gastos": gastos,
        "utilidad": utilidad
    }


# ============================================================
# LISTADO EMPRESAS
# ============================================================

@empresas_bp.route(
    "/empresas"
)
def empresas():

    if "usuario" not in session:
        return redirect(
            "/login"
        )

    empresas = Empresa.query.order_by(
        Empresa.nombre.asc()
    ).all()

    mes = request.args.get(
        "mes",
        ""
    ).strip()

    resumen_empresas = []

    total_ingresos = 0
    total_gastos = 0
    total_utilidad = 0

    for empresa in empresas:

        fila = resumen_empresa(
            empresa,
            mes
        )

        resumen_empresas.append(
            fila
        )

        total_ingresos += (
            fila["ingresos"]
        )

        total_gastos += (
            fila["gastos"]
        )

        total_utilidad += (
            fila["utilidad"]
        )

    error = request.args.get(
        "error",
        ""
    ).strip()

    ok = request.args.get(
        "ok",
        ""
    ).strip()

    return render_template(
        "contabilidad/empresas.html",

        empresas=empresas,

        mes_actual=mes,

        resumen_empresas=resumen_empresas,

        total_ingresos=total_ingresos,

        total_gastos=total_gastos,

        total_utilidad=total_utilidad,

        error=error,

        ok=ok
    )


# ============================================================
# NUEVA EMPRESA
# ============================================================

@empresas_bp.route(
    "/empresas/nueva",
    methods=["GET", "POST"]
)
def nueva_empresa():

    if "usuario" not in session:

        return redirect(
            "/login"
        )

    error = None

    if request.method == "POST":

        nombre = request.form.get(
            "nombre",
            ""
        ).strip().upper()

        if not nombre:

            error = (
                "Debes escribir el nombre de la empresa"
            )

        else:

            existe = Empresa.query.filter_by(
                nombre=nombre
            ).first()

            if existe:

                error = (
                    "Esa empresa ya existe"
                )

            else:

                nueva = Empresa(
                    nombre=nombre
                )

                db.session.add(
                    nueva
                )

                db.session.commit()

                return redirect(
                    "/empresas?ok=Empresa creada correctamente"
                )

    return render_template(
        "contabilidad/nueva_empresa.html",
        error=error
    )


# ============================================================
# EDITAR EMPRESA
# ============================================================

@empresas_bp.route(
    "/empresas/editar/<int:empresa_id>",
    methods=["GET", "POST"]
)
def editar_empresa(empresa_id):

    if "usuario" not in session:

        return redirect(
            "/login"
        )

    empresa = Empresa.query.get_or_404(
        empresa_id
    )

    error = None

    if request.method == "POST":

        nombre = request.form.get(
            "nombre",
            ""
        ).strip().upper()

        if not nombre:

            error = (
                "Debes escribir el nombre de la empresa"
            )

        else:

            existe = Empresa.query.filter(
                Empresa.nombre == nombre,
                Empresa.id != empresa.id
            ).first()

            if existe:

                error = (
                    "Ya existe otra empresa con ese nombre"
                )

            else:

                nombre_anterior = (
                    empresa.nombre
                )

                empresa.nombre = nombre

                db.session.commit()

                if (
                    session.get(
                        "empresa_id"
                    )
                    == empresa.id
                ):

                    session[
                        "empresa_nombre"
                    ] = nombre

                return redirect(
                    f"/empresas?ok=Empresa {nombre_anterior} actualizada correctamente"
                )

    return render_template(
        "contabilidad/editar_empresa.html",
        empresa=empresa,
        error=error
    )


# ============================================================
# ELIMINAR EMPRESA
# ============================================================

@empresas_bp.route(
    "/empresas/eliminar/<int:empresa_id>",
    methods=["POST"]
)
def eliminar_empresa(empresa_id):

    if "usuario" not in session:

        return redirect(
            "/login"
        )

    empresa = Empresa.query.get_or_404(
        empresa_id
    )

    tiene_movimientos = (
        Movimiento.query.filter_by(
            empresa_id=empresa.id
        ).first()
        is not None
    )

    tiene_ventas = (
        VentaEcobike.query.filter_by(
            empresa_id=empresa.id
        ).first()
        is not None
    )

    tiene_sedes = (
        Sede.query.filter_by(
            empresa_id=empresa.id
        ).first()
        is not None
    )

    if (
        tiene_movimientos
        or tiene_ventas
        or tiene_sedes
    ):

        return redirect(
            "/empresas?error=No se puede eliminar la empresa porque ya tiene datos registrados"
        )

    nombre = empresa.nombre

    if (
        session.get(
            "empresa_id"
        )
        == empresa.id
    ):

        session.pop(
            "empresa_id",
            None
        )

        session.pop(
            "empresa_nombre",
            None
        )

    db.session.delete(
        empresa
    )

    db.session.commit()

    return redirect(
        f"/empresas?ok=Empresa {nombre} eliminada correctamente"
    )


# ============================================================
# SELECCIONAR EMPRESA
# ============================================================

@empresas_bp.route(
    "/seleccionar_empresa/<int:empresa_id>"
)
def seleccionar_empresa(empresa_id):

    if "usuario" not in session:

        return redirect(
            "/login"
        )

    empresa = Empresa.query.get_or_404(
        empresa_id
    )

    # --------------------------------------------------------
    # GUARDAR EMPRESA ACTIVA EN LA SESIÓN
    # --------------------------------------------------------

    session[
        "empresa_id"
    ] = empresa.id

    session[
        "empresa_nombre"
    ] = empresa.nombre

    # --------------------------------------------------------
    # REDIRECCIÓN SEGÚN EMPRESA
    # --------------------------------------------------------

    ruta = obtener_ruta_empresa(
        empresa
    )

    return redirect(
        ruta
    )