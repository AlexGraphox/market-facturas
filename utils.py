import csv
import io
import re
import unicodedata


def parse_co_number(v):
    """El export de OficinaPro mezcla formatos: PRECIO viene en formato
    colombiano ('12184,87'), pero IVA y COSTO ya vienen con punto decimal
    ('19.00'). Si hay coma, se asume formato colombiano (punto = miles);
    si no, el punto ya es el separador decimal y se deja tal cual."""
    if v is None:
        return 0.0
    s = str(v).strip()
    if not s:
        return 0.0
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_inventory_csv(file_bytes):
    """Lee el CSV de inventario tal como lo exporta OficinaPro
    (separado por ';', columnas CODIGO;NOMBRE;...;PRECIO;IVA;COSTO;...)."""
    text = None
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = file_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = file_bytes.decode("utf-8", errors="replace")

    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    rows = []
    for r in reader:
        codigo = (r.get("CODIGO") or "").strip()
        nombre = (r.get("NOMBRE") or "").strip()
        if not codigo or not nombre:
            continue
        rows.append({
            "codigo": codigo,
            "nombre": nombre,
            "precio": parse_co_number(r.get("PRECIO")),
            "iva": parse_co_number(r.get("IVA")),
            "costo": parse_co_number(r.get("COSTO")),
        })
    return rows


def csv_escape(value):
    s = "" if value is None else str(value)
    if any(c in s for c in (",", '"', "\n")):
        s = '"' + s.replace('"', '""') + '"'
    return s


def fmt_num(value, decimals=None):
    value = float(value or 0)
    if decimals is not None:
        return f"{value:.{decimals}f}"
    if value.is_integer():
        return str(int(value))
    return str(value)


def sanitize_for_filename(s):
    s = s or ""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^A-Za-z0-9]+", "_", s)
    s = s.strip("_")
    return s or "sd"


def format_fecha_for_filename(fecha):
    m = re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$", (fecha or "").strip())
    if m:
        d, mo, y = m.groups()
        if len(y) == 2:
            y = "20" + y
        return f"{y}{mo.zfill(2)}{d.zfill(2)}"
    return sanitize_for_filename(fecha) or "sinfecha"


def build_filename(meta, sede):
    parts = [
        sanitize_for_filename(meta.get("proveedor")) or "proveedor",
        sanitize_for_filename(meta.get("numero_factura")) or "sinfactura",
        sanitize_for_filename(sede),
        format_fecha_for_filename(meta.get("fecha")),
    ]
    return "_".join(parts) + ".csv"
