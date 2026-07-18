import math
import re
import unicodedata

# Palabras de empaque/medida que aparecen en casi todo el catálogo (no ayudan
# a distinguir un producto de otro), se les baja el peso al comparar.
PACKAGING_STOPWORDS = {
    "X", "UND", "UNDS", "UNIDAD", "UNIDADES", "LATA", "LATAS", "BOTELLA",
    "BOT", "PET", "VIDRIO", "CAJA", "PAQ", "PAQUETE", "GR", "GRS", "KG",
    "ML", "MLS", "LT", "LTS", "L", "CC", "SXP", "PPAL", "REF", "UN",
}


def normalize(s):
    if not s:
        return ""
    s = str(s).upper()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def tokenize(s):
    return [t for t in normalize(s).split(" ") if t]


def compute_idf(inventory):
    df = {}
    for item in inventory:
        for t in set(item["tokens"]):
            df[t] = df.get(t, 0) + 1
    n = len(inventory) or 1
    return {t: math.log((n + 1) / (c + 1)) + 0.1 for t, c in df.items()}


def token_weight(t, idf):
    if any(ch.isdigit() for ch in t):
        return 0.12
    if t in PACKAGING_STOPWORDS:
        return 0.12
    return idf.get(t, 1.5)  # token nunca visto en el inventario: se asume distintivo


def score_match(desc_tokens, inv_tokens, idf):
    set_a, set_b = set(desc_tokens), set(inv_tokens)
    if not set_b:
        return 0.0
    all_tokens = set_a | set_b
    inter_w = union_w = 0.0
    for t in all_tokens:
        w = token_weight(t, idf)
        union_w += w
        if t in set_a and t in set_b:
            inter_w += w
    return inter_w / union_w if union_w else 0.0


def top_matches(query, inventory, idf, n=5):
    """Busca por código interno, código de barras o nombre (en ese orden de
    prioridad) -- productos con el mismo nombre pero distinto código de
    barras (variantes/gramajes) quedan agrupados por delante de coincidencias
    solo parecidas, en vez de mezclados según el puntaje de texto libre."""
    q_raw = (query or "").strip()
    q_norm = normalize(q_raw)
    q_tokens = tokenize(q_raw)
    q_digits = q_raw.replace(" ", "")
    is_digits = q_digits.isdigit()
    # codigo interno es corto (6 digitos): un prefijo de 4 ya distingue bastante.
    # codigo de barras es largo y los primeros digitos son el mismo prefijo de
    # pais/fabricante para decenas de productos -- hace falta escribir mas
    # (7+) antes de que un prefijo empiece a servir para algo.
    codigo_prefix_ok = is_digits and len(q_digits) >= 4
    barra_prefix_ok = is_digits and len(q_digits) >= 7

    tiered = []
    for item in inventory:
        codigo = item.get("codigo") or ""
        barra = item.get("codigo_barra") or ""
        nombre_norm = normalize(item.get("nombre"))

        if q_raw and (q_raw == codigo or q_raw == barra):
            tiered.append((0, 1.0, item))
        elif (codigo_prefix_ok and codigo.startswith(q_digits)) or (barra_prefix_ok and barra and barra.startswith(q_digits)):
            tiered.append((1, 1.0, item))
        elif q_norm and q_norm == nombre_norm:
            tiered.append((1, 1.0, item))
        else:
            score = score_match(q_tokens, item["tokens"], idf)
            if score > 0:
                tiered.append((2, score, item))

    tiered.sort(key=lambda t: (t[0], -t[1]))
    return [(score, item) for _tier, score, item in tiered[:n]]
