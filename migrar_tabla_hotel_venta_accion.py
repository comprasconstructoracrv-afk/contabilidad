from app import create_app
from app.extensions import db


app = create_app()


def migrar_tabla_hotel_venta_accion():
    with app.app_context():
        conn = db.engine.connect()
        trans = conn.begin()

        try:
            print("Iniciando migración de hotel_venta_accion...")

            # 1. revisar si existe tabla vieja
            tablas = conn.exec_driver_sql("""
                SELECT name
                FROM sqlite_master
                WHERE type='table' AND name='hotel_venta_accion'
            """).fetchall()

            if not tablas:
                print("La tabla hotel_venta_accion no existe. No hay nada que migrar.")
                trans.commit()
                return

            # 2. crear tabla nueva temporal con estructura correcta
            conn.exec_driver_sql("""
                CREATE TABLE IF NOT EXISTS hotel_venta_accion_new (
                    id INTEGER PRIMARY KEY,
                    fecha DATE NOT NULL,
                    empresa_id INTEGER NOT NULL,
                    sede_id INTEGER,
                    cliente_id INTEGER,
                    consecutivo_venta INTEGER NOT NULL DEFAULT 1,

                    cliente VARCHAR(150) NOT NULL,
                    cliente_identificacion VARCHAR(50),
                    cliente_direccion VARCHAR(200),
                    cliente_telefono VARCHAR(50),
                    cliente_ciudad VARCHAR(120),
                    cliente_correo VARCHAR(150),

                    descripcion VARCHAR(250) NOT NULL,
                    cantidad_acciones INTEGER NOT NULL DEFAULT 1,

                    valor_unitario_lista FLOAT NOT NULL DEFAULT 0,
                    descuento FLOAT NOT NULL DEFAULT 0,
                    valor_unitario_final FLOAT NOT NULL DEFAULT 0,

                    valor_total_lista FLOAT NOT NULL DEFAULT 0,
                    valor_total_final FLOAT NOT NULL DEFAULT 0,

                    valor_inicial FLOAT NOT NULL DEFAULT 0,
                    valor_recibido FLOAT NOT NULL DEFAULT 0,
                    saldo_pendiente FLOAT NOT NULL DEFAULT 0,

                    financiado BOOLEAN NOT NULL DEFAULT 0,
                    numero_cuotas INTEGER NOT NULL DEFAULT 0,
                    valor_cuota FLOAT NOT NULL DEFAULT 0,
                    fecha_primera_cuota DATE,

                    forma_pago VARCHAR(80),
                    entidad_pago VARCHAR(120),
                    cuenta_destino VARCHAR(150),

                    estado VARCHAR(30) NOT NULL DEFAULT 'PENDIENTE',
                    observacion VARCHAR(300),

                    FOREIGN KEY (empresa_id) REFERENCES empresa (id),
                    FOREIGN KEY (sede_id) REFERENCES sede (id),
                    FOREIGN KEY (cliente_id) REFERENCES hotel_cliente (id)
                )
            """)

            # 3. leer columnas actuales de la tabla vieja
            columnas = conn.exec_driver_sql("""
                PRAGMA table_info(hotel_venta_accion)
            """).fetchall()

            nombres_columnas = [col[1] for col in columnas]
            print("Columnas encontradas en tabla vieja:", nombres_columnas)

            # helpers para usar columna si existe
            def col_o_default(nombre, default_sql):
                if nombre in nombres_columnas:
                    return nombre
                return default_sql

            # 4. copiar datos de vieja a nueva
            sql_insert = f"""
                INSERT INTO hotel_venta_accion_new (
                    id,
                    fecha,
                    empresa_id,
                    sede_id,
                    cliente_id,
                    consecutivo_venta,

                    cliente,
                    cliente_identificacion,
                    cliente_direccion,
                    cliente_telefono,
                    cliente_ciudad,
                    cliente_correo,

                    descripcion,
                    cantidad_acciones,

                    valor_unitario_lista,
                    descuento,
                    valor_unitario_final,

                    valor_total_lista,
                    valor_total_final,

                    valor_inicial,
                    valor_recibido,
                    saldo_pendiente,

                    financiado,
                    numero_cuotas,
                    valor_cuota,
                    fecha_primera_cuota,

                    forma_pago,
                    entidad_pago,
                    cuenta_destino,

                    estado,
                    observacion
                )
                SELECT
                    id,
                    fecha,
                    empresa_id,
                    {col_o_default("sede_id", "NULL")},
                    {col_o_default("cliente_id", "NULL")},
                    {col_o_default("consecutivo_venta", "1")},

                    {col_o_default("cliente", "''")},
                    {col_o_default("cliente_identificacion", "NULL")},
                    {col_o_default("cliente_direccion", "NULL")},
                    {col_o_default("cliente_telefono", "NULL")},
                    {col_o_default("cliente_ciudad", "NULL")},
                    {col_o_default("cliente_correo", "NULL")},

                    {col_o_default("descripcion", "''")},
                    {col_o_default("cantidad_acciones", "1")},

                    {col_o_default("valor_unitario_lista", col_o_default("valor_unitario", "0"))},
                    {col_o_default("descuento", "0")},
                    {col_o_default("valor_unitario_final", col_o_default("valor_unitario", "0"))},

                    {col_o_default("valor_total_lista", col_o_default("valor_total", "0"))},
                    {col_o_default("valor_total_final", col_o_default("valor_total", "0"))},

                    {col_o_default("valor_inicial", col_o_default("valor_recibido_hoy", "0"))},
                    {col_o_default("valor_recibido", col_o_default("valor_recibido_hoy", "0"))},
                    {col_o_default("saldo_pendiente", col_o_default("saldo", "0"))},

                    {col_o_default("financiado", "0")},
                    {col_o_default("numero_cuotas", "0")},
                    {col_o_default("valor_cuota", "0")},
                    {col_o_default("fecha_primera_cuota", "NULL")},

                    {col_o_default("forma_pago", "NULL")},
                    {col_o_default("entidad_pago", "NULL")},
                    {col_o_default("cuenta_destino", "NULL")},

                    {col_o_default("estado", "'PENDIENTE'")},
                    {col_o_default("observacion", "NULL")}
                FROM hotel_venta_accion
            """

            conn.exec_driver_sql(sql_insert)

            # 5. borrar tabla vieja
            conn.exec_driver_sql("DROP TABLE hotel_venta_accion")

            # 6. renombrar tabla nueva
            conn.exec_driver_sql("""
                ALTER TABLE hotel_venta_accion_new
                RENAME TO hotel_venta_accion
            """)

            trans.commit()
            print("Migración completada correctamente.")

        except Exception as e:
            trans.rollback()
            print("Error en migración:", str(e))
            raise

        finally:
            conn.close()


if __name__ == "__main__":
    migrar_tabla_hotel_venta_accion()