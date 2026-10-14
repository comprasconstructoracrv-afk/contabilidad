from app import create_app
from app.extensions import db
from app.models.usuario import Usuario

app = create_app()

with app.app_context():
    db.create_all()

    admin = Usuario.query.filter_by(usuario="admin").first()
    if not admin:
        admin = Usuario(usuario="admin")
        admin.set_password("123456")
        db.session.add(admin)
        db.session.commit()
        print("Usuario admin creado con clave: 123456")
    else:
        print("El usuario admin ya existe.")