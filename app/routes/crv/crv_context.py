from datetime import datetime, date
from io import BytesIO
from pathlib import Path
import calendar
import json
import uuid
import re
from xml.sax.saxutils import escape
from sqlalchemy import text


from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    session,
    flash,
    send_file,
    current_app
)
from werkzeug.utils import secure_filename

try:
    from pypdf import PdfReader
except ImportError:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        PdfReader = None


from app.extensions import db
from app.models.crv_movimiento import CRVMovimiento
from app.models.crv_tercero import CRVTercero
from app.models.sede import Sede
from app.models.crv_cuenta_pagar import CRVCuentaPagar
from app.models.crv_pago_cuenta_pagar import CRVPagoCuentaPagar
from app.models.crv_cuenta_cobrar import CRVCuentaCobrar
from app.models.crv_cobro_cuenta_cobrar import CRVCobroCuentaCobrar
from app.models.crv_proyecto import CRVProyecto
from app.models.crv_cierre_mensual import CRVCierreMensual
from app.models.crv_conciliacion_bancaria import CRVConciliacionBancaria

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak,
    KeepTogether
)


crv_bp = Blueprint(
    "crv",
    "app.routes.crv",
    url_prefix="/crv"
)


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

import pdfplumber

__all__ = [name for name in globals() if not name.startswith("__")]
