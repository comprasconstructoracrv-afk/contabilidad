from app import create_app
from app.extensions import db
from sqlalchemy import text

from app.models.empresa import Empresa
from app.models.empresa_config import EmpresaConfig
from app.models.documento_consecutivo import DocumentoConsecutivo
from app.models.hotel_cliente import HotelCliente
from app.models.hotel_venta_accion import HotelVentaAccion
from app.models.hotel_cuota import HotelCuota
from app.models.hotel_pago_accion import HotelPagoAccion


app = create_app()


def obtener_columnas(tabla):
    resultado = db.session.execute(text(f"PRAGMA table_info({tabla})")).fetchall()
    return [fila[1] for fila in resultado]


def agregar_columna_si_no_existe(tabla, columna, definicion_sql):
    columnas = obtener_columnas(tabla)
    if columna not in columnas:
        sql = f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion_sql}"
        db.session.execute(text(sql))
        db.session.commit()
        print(f"Columna agregada: {tabla}.{columna}")
    else:
        print(f"Columna ya existe: {tabla}.{columna}")


def migrar_tabla_hotel_venta_accion():
    print("Revisando tabla hotel_venta_accion...")

    agregar_columna_si_no_existe("hotel_venta_accion", "cliente_id", "INTEGER")
    agregar_columna_si_no_existe("hotel_venta_accion", "valor_unitario_lista", "FLOAT DEFAULT 0")
    agregar_columna_si_no_existe("hotel_venta_accion", "descuento", "FLOAT DEFAULT 0")
    agregar_columna_si_no_existe("hotel_venta_accion", "valor_unitario_final", "FLOAT DEFAULT 0")
    agregar_columna_si_no_existe("hotel_venta_accion", "valor_total_lista", "FLOAT DEFAULT 0")
    agregar_columna_si_no_existe("hotel_venta_accion", "valor_total_final", "FLOAT DEFAULT 0")
    agregar_columna_si_no_existe("hotel_venta_accion", "valor_inicial", "FLOAT DEFAULT 0")
    agregar_columna_si_no_existe("hotel_venta_accion", "financiado", "BOOLEAN DEFAULT 0")
    agregar_columna_si_no_existe("hotel_venta_accion", "numero_cuotas", "INTEGER DEFAULT 0")
    agregar_columna_si_no_existe("hotel_venta_accion", "valor_cuota", "FLOAT DEFAULT 0")
    agregar_columna_si_no_existe("hotel_venta_accion", "fecha_primera_cuota", "DATE")


def migrar_tabla_hotel_pago_accion():
    print("Revisando tabla hotel_pago_accion...")

    agregar_columna_si_no_existe("hotel_pago_accion", "cliente_id", "INTEGER")
    agregar_columna_si_no_existe("hotel_pago_accion", "cuota_aplicada_numero", "INTEGER")


def asegurar_config_hotel():
    hotel = Empresa.query.filter(Empresa.nombre.ilike("%HOTEL SKY VIEW%")).first()

    if not hotel:
        print("No se encontró la empresa HOTEL SKY VIEW.")
        return

    config = EmpresaConfig.query.filter_by(empresa_id=hotel.id).first()

    if not config:
        config = EmpresaConfig(
            empresa_id=hotel.id,
            nombre_comercial="HOTEL SKY VIEW",
            razon_social="HOTEL SKY VIEW",
            nit="901821623-1",
            direccion="PAYANDE TOLIMA",
            ciudad="PAYANDE TOLIMA",
            telefono="3115901546 - 3114145843",
            correo="ventas@hotelskyview.com | comprasconstructoracrv@gmail.com",
            sitio_web="",
            logo_path="logo_hotel_sky_view.png.jpg",
            color_primario="#17351E",
            color_secundario="#D4AF37",
            color_acento="#FFFFFF",
            tipo_negocio="HOTEL_ACCIONES",
            prefijo_recibo="01",
            texto_nota_recibo=(
                "NOTA ACLARATORIA: Este recibo valida la consignación realizada en la fecha descrita "
                "inicialmente, a la cuenta de ahorros de BANCOLOMBIA N° 718-000020-23 a nombre de "
                "CRV CONSTRUCCIONES Y URBANIZACIONES SAS."
            ),
            firma_elaborado_por="Liseth Romero",
            firma_aprobado_por=""
        )
        db.session.add(config)
        db.session.commit()
        print("Configuración HOTEL SKY VIEW creada.")
    else:
        config.nombre_comercial = "HOTEL SKY VIEW"
        config.razon_social = "HOTEL SKY VIEW"
        config.nit = "901821623-1"
        config.direccion = "PAYANDE TOLIMA"
        config.ciudad = "PAYANDE TOLIMA"
        config.telefono = "3115901546 - 3114145843"
        config.correo = "ventas@hotelskyview.com | comprasconstructoracrv@gmail.com"
        config.sitio_web = ""
        config.logo_path = "logo_hotel_sky_view.png.jpg"
        config.color_primario = "#17351E"
        config.color_secundario = "#D4AF37"
        config.color_acento = "#FFFFFF"
        config.tipo_negocio = "HOTEL_ACCIONES"
        config.prefijo_recibo = "01"
        config.texto_nota_recibo = (
            "NOTA ACLARATORIA: Este recibo valida la consignación realizada en la fecha descrita "
            "inicialmente, a la cuenta de ahorros de BANCOLOMBIA N° 718-000020-23 a nombre de "
            "CRV CONSTRUCCIONES Y URBANIZACIONES SAS."
        )
        config.firma_elaborado_por = "Liseth Romero"
        config.firma_aprobado_por = ""
        db.session.commit()
        print("Configuración HOTEL SKY VIEW actualizada.")

    for tipo in ["VENTA_ACCION_HOTEL", "RECIBO_CAJA_HOTEL"]:
        existe = DocumentoConsecutivo.query.filter_by(
            empresa_id=hotel.id,
            tipo_documento=tipo
        ).first()

        if not existe:
            nuevo = DocumentoConsecutivo(
                empresa_id=hotel.id,
                tipo_documento=tipo,
                siguiente_numero=1
            )
            db.session.add(nuevo)

    db.session.commit()
    print("Consecutivos HOTEL SKY VIEW asegurados.")


def poblar_campos_nuevos_si_faltan():
    print("Ajustando datos antiguos de ventas hotel...")

    ventas = HotelVentaAccion.query.all()

    for venta in ventas:
        if venta.valor_unitario_lista is None:
            venta.valor_unitario_lista = float(venta.valor_unitario_final or 0)

        if venta.valor_unitario_final is None or float(venta.valor_unitario_final or 0) == 0:
            if float(venta.valor_total_final or 0) > 0 and int(venta.cantidad_acciones or 0) > 0:
                venta.valor_unitario_final = float(venta.valor_total_final or 0) / int(venta.cantidad_acciones or 1)
            else:
                venta.valor_unitario_final = float(venta.valor_unitario_lista or 0)

        if venta.valor_total_lista is None or float(venta.valor_total_lista or 0) == 0:
            venta.valor_total_lista = float(venta.valor_unitario_lista or 0) * int(venta.cantidad_acciones or 0)

        if venta.valor_total_final is None or float(venta.valor_total_final or 0) == 0:
            total_base = float(venta.valor_total_lista or 0)
            descuento = float(venta.descuento or 0)
            valor_final = total_base - descuento
            venta.valor_total_final = valor_final if valor_final >= 0 else 0

        if venta.valor_inicial is None:
            venta.valor_inicial = float(venta.valor_recibido or 0)

        if venta.saldo_pendiente is None:
            venta.saldo_pendiente = float(venta.valor_total_final or 0) - float(venta.valor_recibido or 0)

        if venta.saldo_pendiente < 0:
            venta.saldo_pendiente = 0

        if venta.financiado is None:
            venta.financiado = True if float(venta.saldo_pendiente or 0) > 0 else False

        if venta.numero_cuotas is None:
            venta.numero_cuotas = 0

        if venta.valor_cuota is None:
            venta.valor_cuota = 0

        if not venta.estado:
            venta.recalcular_estado()

    db.session.commit()
    print("Ventas antiguas ajustadas a la nueva estructura.")


with app.app_context():
    print("Creando tablas nuevas...")
    db.create_all()
    print("Tablas base creadas correctamente.")

    migrar_tabla_hotel_venta_accion()
    migrar_tabla_hotel_pago_accion()

    asegurar_config_hotel()
    poblar_campos_nuevos_si_faltan()

    print("Migración HOTEL SKY VIEW terminada.")