import streamlit as st
from supabase import create_client, Client

from matching import tokenize

# inventario_stock (la tabla que ya sincroniza OficinaPro) solo trae stock,
# no precio/iva/costo -- la API de OficinaPro que sí los tiene (new_products)
# solo responde a IPs en lista blanca, esta app no puede llamarla directo.
# Por eso el precio/iva/costo vive en esta tabla propia, poblada por upload manual.
DEFAULT_INVENTORY_TABLE = "inventario_precios"


def sign_in(email, password):
    # Cliente nuevo en cada intento de login (no se comparte entre usuarios):
    # con varios cajeros conectados a la vez, un cliente global compartido
    # mezclaría la sesión de uno con la de otro.
    client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])
    return client.auth.sign_in_with_password({"email": email, "password": password})


@st.cache_resource
def _service_client() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_SERVICE_ROLE_KEY"])


@st.cache_data(ttl=300)
def load_inventory():
    table = st.secrets.get("INVENTORY_TABLE", DEFAULT_INVENTORY_TABLE)
    res = _service_client().table(table).select("*").execute()
    inventory = []
    for r in res.data or []:
        codigo = str(r.get("codigo") or "").strip()
        nombre = str(r.get("nombre") or "").strip()
        if not codigo or not nombre:
            continue
        inventory.append({
            "codigo": codigo,
            "nombre": nombre,
            "precio_venta": float(r.get("precio") or 0),
            "iva": float(r.get("iva") or 0),
            "costo_actual": float(r.get("costo") or 0),
            "tokens": tokenize(nombre),
        })
    return inventory


def upsert_inventory_prices(rows):
    if not rows:
        return
    table = st.secrets.get("INVENTORY_TABLE", DEFAULT_INVENTORY_TABLE)
    client = _service_client()
    batch = 500
    for i in range(0, len(rows), batch):
        client.table(table).upsert(rows[i:i + batch], on_conflict="codigo").execute()
    load_inventory.clear()


def log_factura(usuario_email, proveedor, numero_factura, fecha_factura, sede, total_lineas, lineas_sin_match):
    _service_client().table("facturas_generadas").insert({
        "usuario_email": usuario_email,
        "proveedor": proveedor,
        "numero_factura": numero_factura,
        "fecha_factura": fecha_factura,
        "sede": sede,
        "total_lineas": total_lineas,
        "lineas_sin_match": lineas_sin_match,
    }).execute()
