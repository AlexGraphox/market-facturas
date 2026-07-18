import streamlit as st

import claude_extract
import matching
import supa
from utils import build_filename, csv_escape, fmt_num, parse_inventory_csv

st.set_page_config(page_title="Facturas SM Market", page_icon="🧾", layout="wide")

SEDES = ["Samaria", "Playa Dormida", "Two Towers"]


def rk(prefix, row_id):
    """Key de widget con el id de la corrida actual, para que una factura nueva
    nunca herede valores editados de la factura anterior."""
    return f"{prefix}_{st.session_state.batch_id}_{row_id}"


def confidence_label(row, selected_codigo):
    if selected_codigo is None:
        return ":red[Sin producto]"
    if selected_codigo == row["best_codigo"]:
        score = row["best_score"]
        if score >= 0.55:
            return f":green[{round(score * 100)}% match]"
        if score >= 0.28:
            return f":orange[{round(score * 100)}% match]"
        return f":red[{round(score * 100)}% match]"
    return ":blue[Asignado a mano]"


def alerts_for_row(costo, iva_pct, cantidad, valor_total, inv_item):
    alerts = []
    if inv_item:
        costo_actual = inv_item["costo_actual"]
        if costo_actual > 0:
            delta = costo - costo_actual
            if abs(delta) >= 1:
                pct = (delta / costo_actual) * 100
                sign = "+" if delta > 0 else ""
                alerts.append(f"costo {sign}{pct:.1f}% vs inventario (${costo_actual:.2f})")
        if abs(inv_item["iva"] - iva_pct) >= 0.5:
            alerts.append(f"IVA factura {iva_pct}% ≠ inventario {inv_item['iva']}%")
    if valor_total and valor_total > 0:
        expected = cantidad * costo * (1 + iva_pct / 100)
        if expected > valor_total * 1.01:
            alerts.append(f"revisar total: esperado ${expected:.2f}, factura dice ${valor_total:.2f}")
    return alerts


def login_screen():
    st.title("🧾 Facturas de proveedor — SM Market")
    st.caption("Inicia sesión con tu correo autorizado.")
    with st.form("login_form"):
        email = st.text_input("Correo electrónico")
        password = st.text_input("Clave", type="password")
        submitted = st.form_submit_button("Entrar", type="primary")
    if submitted:
        try:
            result = supa.sign_in(email.strip(), password)
            st.session_state.auth = {"email": result.user.email}
            st.rerun()
        except Exception:
            st.error("Correo o clave incorrectos, o el usuario todavía no existe.")


def main():
    if "auth" not in st.session_state:
        st.session_state.auth = None
    if not st.session_state.auth:
        login_screen()
        st.stop()

    if "rows" not in st.session_state:
        st.session_state.rows = []
    if "invoice_meta" not in st.session_state:
        st.session_state.invoice_meta = {}
    if "batch_id" not in st.session_state:
        st.session_state.batch_id = 0
    if "uploader_version" not in st.session_state:
        st.session_state.uploader_version = 0

    with st.sidebar:
        st.write(f"Sesión: **{st.session_state.auth['email']}**")
        if st.button("Cerrar sesión"):
            st.session_state.auth = None
            st.rerun()

    st.title("🧾 Facturas de proveedor — SM Market")

    with st.expander("Actualizar inventario compartido (precios y costos)"):
        st.caption(
            "Sube el mismo CSV que exportas de OficinaPro. Se actualiza para todos los usuarios — "
            "solo hace falta subirlo cuando cambien precios o costos, no en cada factura."
        )
        inv_file = st.file_uploader("CSV de inventario", type=["csv"], key="inv_upload")
        if st.button("Actualizar inventario", disabled=inv_file is None):
            try:
                rows = parse_inventory_csv(inv_file.getvalue())
                if not rows:
                    st.error("No se reconocieron columnas CODIGO/NOMBRE/PRECIO/IVA/COSTO en el archivo.")
                else:
                    supa.upsert_inventory_prices(rows)
                    st.success(f"Inventario actualizado: {len(rows)} productos.")
                    st.rerun()
            except Exception as e:
                st.error(f"Error leyendo el archivo: {e}")

    inventory = supa.load_inventory()
    idf = matching.compute_idf(inventory)
    inv_by_codigo = {item["codigo"]: item for item in inventory}
    st.caption(f"Inventario: {len(inventory)} productos (actualízalo arriba si cambiaron precios/costos).")

    st.divider()
    st.subheader("1. Factura del proveedor")
    uploaded = st.file_uploader(
        "Sube la factura en PDF o imagen",
        type=["pdf", "png", "jpg", "jpeg", "webp"],
        key=f"invoice_file_{st.session_state.uploader_version}",
    )
    extract_clicked = st.button("Extraer productos", type="primary", disabled=uploaded is None)

    if extract_clicked and uploaded is not None:
        with st.spinner("Leyendo la factura y extrayendo productos…"):
            try:
                parsed, raw = claude_extract.extract_invoice(uploaded.getvalue(), uploaded.type)
            except Exception as e:
                st.error(f"Error al conectar con el servicio de extracción: {e}")
                parsed, raw = None, None

        if parsed is None and raw is not None:
            st.error(
                "No se pudo interpretar la respuesta como JSON. Puede que la factura tenga demasiados "
                "renglones o la imagen no sea legible. Respuesta recibida:\n\n" + raw[:500]
            )
        elif parsed is not None:
            items = parsed.get("items") or []
            if not items:
                st.error("No se detectaron productos en la factura. Intenta con una imagen más nítida.")
            else:
                st.session_state.invoice_meta = {
                    "proveedor": parsed.get("proveedor", ""),
                    "numero_factura": parsed.get("numero_factura", ""),
                    "fecha": parsed.get("fecha", ""),
                }
                st.session_state.batch_id += 1
                rows = []
                for i, it in enumerate(items):
                    desc = it.get("descripcion") or it.get("codigo_proveedor") or ""
                    matches = matching.top_matches(desc, inventory, idf, n=1)
                    best_score, best_item = matches[0] if matches else (0.0, None)
                    rows.append({
                        "id": i,
                        "descripcion": desc,
                        "codigo_proveedor": it.get("codigo_proveedor", ""),
                        "cantidad": float(it.get("cantidad") or 0),
                        "costo": float(it.get("precio_unitario") or 0),
                        "iva_pct": float(it.get("iva_pct") or 0),
                        "valor_total": float(it.get("valor_total") or 0),
                        "best_codigo": best_item["codigo"] if best_item and best_score > 0 else None,
                        "best_score": best_score,
                    })
                st.session_state.rows = rows
                st.success(f"{len(rows)} productos detectados.")

    if not st.session_state.rows:
        return

    st.divider()
    meta = st.session_state.invoice_meta
    header_col, reset_col = st.columns([5, 1])
    header_col.subheader("2. Revisa y confirma")
    if reset_col.button("↺ Nueva factura", help="Descarta esta factura y sube otra, sin salir de la sesión"):
        st.session_state.rows = []
        st.session_state.invoice_meta = {}
        st.session_state.uploader_version += 1
        st.rerun()
    m1, m2, m3 = st.columns(3)
    m1.metric("Proveedor", meta.get("proveedor") or "—")
    m2.metric("Factura N°", meta.get("numero_factura") or "—")
    m3.metric("Fecha", meta.get("fecha") or "—")

    codigo_label = {item["codigo"]: f'{item["nombre"]} — {item["codigo"]}' for item in inventory}
    sin_match_count = 0
    total_sin_iva = 0.0
    total_con_iva = 0.0

    for row in st.session_state.rows:
        rid = row["id"]
        excl_key, sel_key = rk("excl", rid), rk("sel", rid)
        cant_key, costo_key = rk("cant", rid), rk("costo", rid)
        iva_key, precio_key = rk("iva", rid), rk("precio", rid)

        st.session_state.setdefault(excl_key, False)
        st.session_state.setdefault(sel_key, row["best_codigo"])
        st.session_state.setdefault(cant_key, row["cantidad"])
        st.session_state.setdefault(costo_key, row["costo"])
        st.session_state.setdefault(iva_key, row["iva_pct"])
        default_precio = inv_by_codigo[row["best_codigo"]]["precio_venta"] if row["best_codigo"] in inv_by_codigo else 0.0
        st.session_state.setdefault(precio_key, default_precio)

        with st.container(border=True):
            top = st.columns([0.6, 2.6, 3])
            top[0].checkbox("Excluir", key=excl_key)
            top[1].markdown(
                f"**{row['descripcion']}**  \n"
                f":gray[cod. proveedor: {row['codigo_proveedor'] or '—'}]"
            )
            with top[2]:
                query = st.text_input(
                    "Buscar producto",
                    key=rk("q", rid),
                    placeholder="Escribe para buscar por nombre…",
                    label_visibility="collapsed",
                )
                # Sin búsqueda: candidatos cercanos a la descripción de la factura.
                # Con búsqueda: se limita a lo que escribió el cajero (no la lista completa).
                if query.strip():
                    found = matching.top_matches(query, inventory, idf, n=15)
                else:
                    found = matching.top_matches(row["descripcion"], inventory, idf, n=8)
                options = [None] + [it["codigo"] for score, it in found if score > 0]

                # El valor actual siempre debe seguir siendo una opción válida,
                # aunque no aparezca entre los resultados de una búsqueda nueva.
                current = st.session_state.get(sel_key)
                if current is not None and current not in options:
                    options.append(current)
                if row["best_codigo"] and row["best_codigo"] not in options:
                    options.append(row["best_codigo"])

                selected = st.selectbox(
                    "Producto en inventario",
                    options=options,
                    format_func=lambda c: "— sin coincidencia, dejar en blanco —" if c is None else codigo_label.get(c, c),
                    key=sel_key,
                    label_visibility="collapsed",
                )
                if query.strip() and len(options) == 1:
                    st.caption("Sin resultados para esa búsqueda — puedes dejarlo en blanco.")
                else:
                    st.caption(confidence_label(row, selected))
            if selected is None:
                sin_match_count += 1

            bottom = st.columns(4)
            cantidad = bottom[0].number_input("Cantidad", key=cant_key, step=1.0, format="%.2f")
            costo = bottom[1].number_input("Costo unit.", key=costo_key, step=0.01, format="%.2f")
            iva_pct = bottom[2].number_input("IVA %", key=iva_key, step=0.01, format="%.2f")
            precio_venta = bottom[3].number_input("Precio venta (sin IVA)", key=precio_key, step=0.01, format="%.2f")
            bottom[3].caption(f"Con IVA (así se exporta al CSV): **${precio_venta * (1 + iva_pct / 100):,.2f}**")

            subtotal = cantidad * costo
            subtotal_con_iva = subtotal * (1 + iva_pct / 100)
            st.caption(f"Total línea: ${subtotal:,.2f} sin IVA  ·  ${subtotal_con_iva:,.2f} con IVA — compáralo con lo impreso en esta línea de la factura")

            inv_item = inv_by_codigo.get(selected)
            alerts = alerts_for_row(costo, iva_pct, cantidad, row["valor_total"], inv_item)
            if alerts:
                st.caption("⚠️ " + " · ".join(alerts))

        # Acumulado de TODA la factura capturada (incluidas o no), para comparar
        # contra lo impreso -- unos proveedores imprimen el total con IVA, otros sin IVA.
        total_sin_iva += subtotal
        total_con_iva += subtotal_con_iva

    if sin_match_count:
        st.warning(
            f"{sin_match_count} línea(s) sin producto asignado. Se exportarán con el nombre de la factura "
            "y sin código — al importar en OficinaPro deberás crear esos productos ahí."
        )

    tc1, tc2 = st.columns(2)
    tc1.metric("Total factura (sin IVA)", f"${total_sin_iva:,.2f}")
    tc2.metric("Total factura (con IVA)", f"${total_con_iva:,.2f}")
    st.caption("Compara contra el total impreso en la factura del proveedor — según el proveedor, imprime uno u otro.")

    st.divider()
    st.subheader("3. Exportar")
    sede = st.selectbox("Sede", [""] + SEDES)
    incluidas = [r for r in st.session_state.rows if not st.session_state.get(rk("excl", r["id"]))]
    st.caption(f"{len(incluidas)} de {len(st.session_state.rows)} líneas a exportar")

    if st.button("Generar CSV para OficinaPro", type="primary", disabled=not sede):
        lines = ["codigo unico,nombre,costo,iva %,cantidad,precio de venta"]
        for row in incluidas:
            rid = row["id"]
            selected = st.session_state.get(rk("sel", rid))
            cantidad = st.session_state.get(rk("cant", rid))
            costo = st.session_state.get(rk("costo", rid))
            iva_pct = st.session_state.get(rk("iva", rid))
            precio_venta = st.session_state.get(rk("precio", rid))
            if selected and selected in inv_by_codigo:
                codigo_out, nombre_out = selected, inv_by_codigo[selected]["nombre"]
            else:
                codigo_out, nombre_out = "", row["descripcion"]
            # OficinaPro espera "precio de venta" con IVA incluido; en pantalla se
            # maneja sin IVA (igual que costo/margen), se le suma solo al exportar.
            precio_con_iva = precio_venta * (1 + iva_pct / 100)
            lines.append(",".join([
                csv_escape(codigo_out),
                csv_escape(nombre_out),
                fmt_num(costo, 2),
                fmt_num(iva_pct),
                fmt_num(cantidad),
                fmt_num(precio_con_iva, 2),
            ]))
        csv_text = "\n".join(lines)
        filename = build_filename(meta, sede)

        try:
            supa.log_factura(
                usuario_email=st.session_state.auth["email"],
                proveedor=meta.get("proveedor", ""),
                numero_factura=meta.get("numero_factura", ""),
                fecha_factura=meta.get("fecha", ""),
                sede=sede,
                total_lineas=len(incluidas),
                lineas_sin_match=sin_match_count,
            )
        except Exception as e:
            st.warning(f"El CSV se generó, pero no se pudo guardar el registro de auditoría: {e}")

        st.success(f"Archivo generado: {len(incluidas)} productos listos para importar.")
        st.download_button(
            "Descargar " + filename,
            data=csv_text.encode("utf-8-sig"),
            file_name=filename,
            mime="text/csv",
        )


main()
