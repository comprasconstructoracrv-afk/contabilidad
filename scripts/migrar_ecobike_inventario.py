import sqlite3
from pathlib import Path

DB_PATH = Path("instance/contabilidad.db")

columnas_producto = {
    "tipo_producto": "VARCHAR(30) DEFAULT 'BICICLETA'",
    "marca": "VARCHAR(100)",
    "modelo": "VARCHAR(100)",
    "color": "VARCHAR(80)",
    "talla": "VARCHAR(50)",
    "serial": "VARCHAR(120)",
    "precio_venta": "FLOAT DEFAULT 0",
    "stock_minimo": "INTEGER DEFAULT 0",
    "activo": "BOOLEAN DEFAULT 1",
}

def columna_existe(cursor, tabla, columna):
    cursor.execute(f"PRAGMA table_info({tabla})")
    columnas = [fila[1] for fila in cursor.fetchall()]
    return columna in columnas

def agregar_columna(cursor, tabla, columna, definicion):
    if not columna_existe(cursor, tabla, columna):
        cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")
        print(f"OK: columna agregada {tabla}.{columna}")
    else:
        print(f"YA EXISTE: {tabla}.{columna}")

def crear_tabla_inventario(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventario_ecobike (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER NOT NULL,
            producto_id INTEGER NOT NULL,
            sede_id INTEGER,
            ubicacion VARCHAR(30) NOT NULL DEFAULT 'SEDE',
            cantidad INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(empresa_id) REFERENCES empresa(id),
            FOREIGN KEY(producto_id) REFERENCES producto_ecobike(id),
            FOREIGN KEY(sede_id) REFERENCES sede(id)
        )
    """)
    print("OK: tabla inventario_ecobike verificada")

def crear_tabla_movimientos(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimiento_inventario_ecobike (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha DATETIME NOT NULL,
            empresa_id INTEGER NOT NULL,
            producto_id INTEGER NOT NULL,
            sede_origen_id INTEGER,
            sede_destino_id INTEGER,
            tipo_movimiento VARCHAR(40) NOT NULL,
            cantidad INTEGER NOT NULL DEFAULT 0,
            observacion VARCHAR(250),
            FOREIGN KEY(empresa_id) REFERENCES empresa(id),
            FOREIGN KEY(producto_id) REFERENCES producto_ecobike(id),
            FOREIGN KEY(sede_origen_id) REFERENCES sede(id),
            FOREIGN KEY(sede_destino_id) REFERENCES sede(id)
        )
    """)
    print("OK: tabla movimiento_inventario_ecobike verificada")

def main():
    if not DB_PATH.exists():
        print(f"ERROR: no existe la base de datos en {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for columna, definicion in columnas_producto.items():
        agregar_columna(cursor, "producto_ecobike", columna, definicion)

    crear_tabla_inventario(cursor)
    crear_tabla_movimientos(cursor)

    conn.commit()
    conn.close()

    print("MIGRACION ECOBIKE COMPLETADA")

if __name__ == "__main__":
    main()