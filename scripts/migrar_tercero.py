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

if "tercero" not in columnas:
    cursor.execute("ALTER TABLE movimiento ADD COLUMN tercero VARCHAR(150)")
    print("Columna tercero agregada a movimiento.")
else:
    print("La columna tercero ya existe.")

conexion.commit()
conexion.close()
print("Migración finalizada correctamente.")