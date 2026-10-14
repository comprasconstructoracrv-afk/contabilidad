from app import create_app
from app.extensions import db
from app.models.empresa import Empresa
from app.models.producto_ecobike import ProductoEcobike

app = create_app()

catalogo = [
    ("ECO FORCE", 1382736),
    ("ECO SMART", 1434586),
    ("ECO EXPERT PRO", 1235828),
    ("ECO VOLT", 1521003),
    ("ECO RIDE", 1183978),
    ("ECO PLUS", 2091422),
    ("ECO EPIC", 1183978),
    ("ECO GOLF", 2349957),
    ("ECO EMOTION", 1292149),
    ("VOITRUNNER", 1373729),
    ("TRIVOLT", 1614175),
    ("ECO CLASSIC", 1201982),
]

with app.app_context():
    db.create_all()

    ecobike = Empresa.query.filter_by(nombre="ECOBIKE").first()

    if not ecobike:
        print("No existe la empresa ECOBIKE.")
    else:
        for referencia, costo in catalogo:
            existe = ProductoEcobike.query.filter_by(
                referencia=referencia,
                empresa_id=ecobike.id
            ).first()

            if not existe:
                db.session.add(
                    ProductoEcobike(
                        referencia=referencia,
                        costo_compra=costo,
                        empresa_id=ecobike.id
                    )
                )

        db.session.commit()
        print("Catálogo ECOBIKE cargado correctamente.")