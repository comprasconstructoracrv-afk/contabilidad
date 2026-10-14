from app import create_app
from app.extensions import db
from app.models.empresa import Empresa

app = create_app()

with app.app_context():
    db.create_all()

    empresas_iniciales = [
        "CRV",
        "ECOBIKE",
        "COMERCIALIZADORA",
        "HOTEL"
    ]

    for nombre in empresas_iniciales:
        existe = Empresa.query.filter_by(nombre=nombre).first()
        if not existe:
            db.session.add(Empresa(nombre=nombre))

    db.session.commit()
    print("Empresas cargadas correctamente.")