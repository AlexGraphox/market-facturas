import base64
import json

import streamlit as st
from anthropic import Anthropic

INSTRUCTION = (
    "Esta es una factura de compra de un proveedor colombiano. "
    "Extrae SOLO los renglones de productos (ignora totales, retenciones, observaciones, firmas). "
    "Responde UNICAMENTE con JSON compacto valido, sin texto adicional, sin bloques de codigo markdown, con esta forma exacta: "
    '{"proveedor":"","numero_factura":"","fecha":"","items":[{"codigo_proveedor":"","descripcion":"","cantidad":0,"precio_unitario":0,"iva_pct":0,"valor_total":0}]}. '
    "precio_unitario es el valor unitario ANTES de IVA, tal como aparece impreso (columna \"Precio Unitario\" o equivalente), "
    "con TODOS sus decimales exactos - nunca lo calcules dividiendo el total entre la cantidad, copialo literal. "
    "valor_total es el valor total de esa linea tal como aparece impreso (columna \"Valor Total\"), tambien con todos sus decimales, sin recalcularlo. "
    "iva_pct es el porcentaje de IVA de esa linea (ej: 19, 5 o 0), como numero, no texto. cantidad como numero. "
    "La precision decimal es critica: estos numeros se usan para cuadrar el total de la factura, asi que transcribe cada cifra "
    "exactamente como esta impresa, sin redondear. No inventes datos: si un campo no aparece, usa \"\" o 0."
)


@st.cache_resource
def _client():
    return Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])


def extract_invoice(file_bytes, media_type):
    """Devuelve (parsed_json, raw_text). Si el parseo falla, parsed_json es None
    y raw_text trae la respuesta cruda para mostrarla al usuario."""
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    if media_type == "application/pdf":
        content_block = {"type": "document", "source": {"type": "base64", "media_type": media_type, "data": b64}}
    else:
        content_block = {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}}

    response = _client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": [content_block, {"type": "text", "text": INSTRUCTION}]}],
    )
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    clean = text
    for fence in ("```json", "```"):
        if clean.startswith(fence):
            clean = clean[len(fence):]
    if clean.endswith("```"):
        clean = clean[:-3]
    clean = clean.strip()

    try:
        return json.loads(clean), None
    except json.JSONDecodeError:
        return None, clean
