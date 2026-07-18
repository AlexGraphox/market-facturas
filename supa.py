import streamlit as st
from supabase import create_client, Client

from matching import tokenize

# Si los nombres de columna en Supabase no coinciden con estos, ajustar aquí
# (no hace falta tocar el resto del código).
INVENTORY_COLUMNS = {
    "codigo": "codigo",
    "nombre": "nombre",
    "precio": "precio",
    "iva": "iva",
    "costo": "costo",
}


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
    table = st.secrets.get("INVENTORY_TABLE", "inventario_stock")
    res = _service_client().table(table).select("*").execute()
    c = INVENTORY_COLUMNS
    inventory = []
    for r in res.data or []:
        codigo = str(r.get(c["codigo"]) or "").strip()
        nombre = str(r.get(c["nombre"]) or "").strip()
        if not codigo or not nombre:
            continue
        inventory.append({
            "codigo": codigo,
            "nombre": nombre,
            "precio_venta": float(r.get(c["precio"]) or 0),
            "iva": float(r.get(c["iva"]) or 0),
            "costo_actual": float(r.get(c["costo"]) or 0),
            "tokens": tokenize(nombre),
        })
    return inventory


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
