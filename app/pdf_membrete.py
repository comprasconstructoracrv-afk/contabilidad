import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape


EMPRESA_MBRETE = {
    "razon_social": "CONSTRUCCIONES Y URBANIZACIONES S.A.S",
    "nit": "901.527.083-2",
    "direccion": "AV. AMBALA N° 27-136 - PISO 3",
    "ciudad": "IBAGUÉ - TOLIMA",
    "telefono": "311 414 5843",
}

COLOR_AZUL = colors.HexColor("#18293D")
COLOR_DORADO = colors.HexColor("#D4AF37")
COLOR_DORADO_SUAVE = colors.HexColor("#E9C95C")
COLOR_GRIS = colors.HexColor("#6B7280")
COLOR_BORDE = colors.HexColor("#D9E1EA")


def obtener_logo_path(current_app):
    return os.path.join(current_app.root_path, "static", "logo_crv.png")


def dibujar_logo(pdf, current_app, x=35, y=710, ancho=95, alto=58):
    logo_path = obtener_logo_path(current_app)
    if os.path.exists(logo_path):
        try:
            pdf.drawImage(
                logo_path,
                x,
                y,
                width=ancho,
                height=alto,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            pass


def dibujar_membrete(pdf, current_app, empresa_nombre, titulo, subtitulo="", horizontal=False):
    if horizontal:
        width, height = landscape(letter)
    else:
        width, height = letter

    logo_y = height - 92
    dibujar_logo(pdf, current_app, x=34, y=logo_y, ancho=92, alto=55)

    # bloque central empresa
    pdf.setFont("Helvetica-Bold", 11)
    pdf.setFillColor(COLOR_AZUL)
    pdf.drawCentredString(width / 2, height - 42, EMPRESA_MBRETE["razon_social"])

    pdf.setFont("Helvetica-Bold", 10)
    pdf.setFillColor(colors.black)
    pdf.drawCentredString(width / 2, height - 57, f"NIT: {EMPRESA_MBRETE['nit']}")
    pdf.drawCentredString(width / 2, height - 72, EMPRESA_MBRETE["direccion"])
    pdf.drawCentredString(width / 2, height - 87, EMPRESA_MBRETE["ciudad"])
    pdf.drawCentredString(width / 2, height - 102, f"TELÉFONO: {EMPRESA_MBRETE['telefono']}")

    # franja dorada derecha más ancha y mejor alineada
    badge_width = 190
    badge_height = 24
    badge_x = width - badge_width - 34
    badge_y = height - 82

    pdf.setFillColor(COLOR_DORADO_SUAVE)
    pdf.roundRect(badge_x, badge_y, badge_width, badge_height, 11, stroke=0, fill=1)

    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(badge_x + (badge_width / 2), badge_y + 8, titulo.upper())

    # título principal más pequeño y más elegante
    pdf.setFillColor(COLOR_AZUL)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(34, height - 132, f"{empresa_nombre} - {titulo}")

    if subtitulo:
        pdf.setFont("Helvetica", 9)
        pdf.setFillColor(COLOR_GRIS)
        pdf.drawString(34, height - 147, subtitulo)

    # línea separadora
    pdf.setStrokeColor(COLOR_BORDE)
    pdf.setLineWidth(1)
    pdf.line(34, height - 160, width - 34, height - 160)

    return height - 184


def dibujar_resumen_pdf(pdf, x, y, ancho, alto, titulo, valor):
    pdf.setFillColor(colors.white)
    pdf.setStrokeColor(COLOR_BORDE)
    pdf.roundRect(x, y - alto, ancho, alto, 12, stroke=1, fill=1)

    pdf.setFillColor(COLOR_DORADO)
    pdf.rect(x, y - 4, ancho, 4, stroke=0, fill=1)

    pdf.setFillColor(COLOR_AZUL)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(x + 12, y - 22, titulo)

    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(x + 12, y - 42, valor)