import sqlite3
from pathlib import Path

db_path = Path("instance/contabilidad.db")

if not db_path.exists():
    print("No existe la base de datos en instance/contabilidad.db")
    raise SystemExit

conexion = sqlite3.connect(db_path)
cursor = conexion.cursor()

cursor.execute("PRAGMA table_info(venta_ecobike)")
columnas = [fila[1] for fila in cursor.fetchall()]

nuevas_columnas = [
    ("descuento", "FLOAT DEFAULT 0"),
    ("cliente_cedula", "VARCHAR(50)"),
    ("cliente_direccion", "VARCHAR(200)"),
    ("cliente_celular", "VARCHAR(50)"),
    ("cliente_correo", "VARCHAR(120)")
]

for nombre, tipo in nuevas_columnas:
    if nombre not in columnas:
        cursor.execute(f"ALTER TABLE venta_ecobike ADD COLUMN {nombre} {tipo}")
        print(f"Columna {nombre} agregada.")
    else:
        print(f"La columna {nombre} ya existe.")

conexion.commit()
conexion.close()
print("Migración finalizada correctamente.")