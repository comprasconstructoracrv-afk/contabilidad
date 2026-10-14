from flask import Blueprint, render_template, request, redirect, session
from app.extensions import db
from app.models.usuario import Usuario

auth_bp = Blueprint("auth_bp", __name__)


@auth_bp.route("/")
def inicio():
    return redirect("/login")


def asegurar_admin():
    admin = Usuario.query.filter_by(usuario="admin").first()
    if not admin:
        admin = Usuario(usuario="admin")
        admin.set_password("123456")
        db.session.add(admin)
        db.session.commit()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    asegurar_admin()
    error = None

    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        password = request.form.get("password", "").strip()

        user = Usuario.query.filter_by(usuario=usuario).first()

        if user and user.check_password(password):
            session["usuario"] = user.usuario
            session.pop("empresa_id", None)
            session.pop("empresa_nombre", None)
            return redirect("/empresas")
        else:
            error = "Usuario o contraseña incorrectos"

    return render_template("contabilidad/login.html", error=error)


@auth_bp.route("/cambiar-password", methods=["GET", "POST"])
def cambiar_password():
    if "usuario" not in session:
        return redirect("/login")

    error = None
    ok = None

    if request.method == "POST":
        actual = request.form.get("actual", "").strip()
        nueva = request.form.get("nueva", "").strip()
        confirmar = request.form.get("confirmar", "").strip()

        user = Usuario.query.filter_by(usuario=session["usuario"]).first()

        if not user:
            return redirect("/login")

        if not user.check_password(actual):
            error = "La contraseña actual no es correcta"
        elif len(nueva) < 4:
            error = "La nueva contraseña debe tener al menos 4 caracteres"
        elif nueva != confirmar:
            error = "La confirmación no coincide"
        else:
            user.set_password(nueva)
            db.session.commit()
            ok = "Contraseña actualizada correctamente"

    return render_template("contabilidad/cambiar_password.html", error=error, ok=ok)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/login")