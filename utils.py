import re
import unicodedata


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
