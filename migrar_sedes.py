import sqlite3
from pathlib import Path

db_path = Path("instance/contabilidad.db")

if not db_path.exists():
    print("No existe la base de datos en instance/contabilidad.db")
    raise SystemExit

conexion = sqlite3.connect(db_path)
cursor = conexion.cursor()

cursor.execute("PRAGMA table_info(movimiento)")
columnas = [fila[1] for fila in cursor.fetchall()]

if "sede_id" not in columnas:
    cursor.execute("ALTER TABLE movimiento ADD COLUMN sede_id INTEGER")
    print("Columna sede_id agregada a movimiento.")
else:
    print("La columna sede_id ya existe.")

conexion.commit()
conexion.close()

from app import create_app
from app.extensions import db
from app.models.empresa import Empresa
from app.models.sede import Sede

app = create_app()

with app.app_context():
    db.create_all()

    ecobike = Empresa.query.filter_by(nombre="ECOBIKE").first()

    if ecobike:
        sedes_iniciales = [
            "SEDE IBAGUE",
            "SEDE GIRARDOT",
            "SEDE ESPINAL"
        ]

        for nombre_sede in sedes_iniciales:
            existe = Sede.query.filter_by(nombre=nombre_sede, empresa_id=ecobike.id).first()
            if not existe:
                db.session.add(Sede(nombre=nombre_sede, empresa_id=ecobike.id))

        db.session.commit()
        print("Sedes de ECOBIKE cargadas correctamente.")
    else:
        print("No se encontró la empresa ECOBIKE. Cárgala primero.")