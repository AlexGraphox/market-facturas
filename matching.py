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


def top_matches(desc, inventory, idf, n=5):
    desc_tokens = tokenize(desc)
    scored = [(score_match(desc_tokens, item["tokens"], idf), item) for item in inventory]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:n]
