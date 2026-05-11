import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

# ─── CONFIGURACIÓN VISUAL ─────────────────────────────────────────────────────
st.set_page_config(page_title="UPES - Control de Aulas", layout="wide")

st.markdown("""
<style>
    .bloque { padding: 15px; border-radius: 10px; margin-bottom: 8px; border: 1px solid #ddd; font-family: sans-serif; }
    .clase { background-color: #ffebee; color: #b71c1c; border-left: 6px solid #b71c1c; }
    .libre { background-color: #e8f5e9; color: #1b5e20; border-left: 6px solid #1b5e20; }
    .reserva { background-color: #fff9c4; color: #827717; border-left: 6px solid #fbc02d; font-weight: bold; }
    .time-badge { font-weight: bold; margin-right: 12px; font-size: 1.1em; }
</style>
""", unsafe_allow_html=True)

def normalizar(t):
    """Limpia el texto para que 'A-21' coincida con 'A 21' o 'A21'."""
    if pd.isna(t): return ""
    return "".join(filter(str.isalnum, str(t))).upper()

@st.cache_data(ttl=10)
def cargar_todo():
    # 1. CARGAR RESERVAS (GOOGLE SHEETS)
    url_res = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
    df_res = pd.DataFrame()
    try:
        r = requests.get(url_res).text.splitlines()
        idx = next(i for i, line in enumerate(r) if "Marca temporal" in line)
        tmp = pd.read_csv(io.StringIO("\n".join(r[idx:])))
        df_res['act'] = tmp.iloc[:, 4]
        df_res['fec'] = pd.to_datetime(tmp.iloc[:, 6], dayfirst=True, errors='coerce').dt.date
        df_res['aula'] = tmp.iloc[:, 7].apply(normalizar)
        df_res['ini'] = tmp.iloc[:, 8].astype(str)
        df_res['fin'] = tmp.iloc[:, 9].astype(str)
        df_res['user'] = tmp.iloc[:, 3]
    except: pass

    # 2. CARGAR HORARIO (GITHUB)
    url_hor = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"
    df_hor = pd.DataFrame()
    aulas_reales = []
    try:
        resp = requests.get(url_hor)
        xl = pd.read_excel(io.BytesIO(resp.content))
        xl["Dia"] = xl["Dia"].ffill()
        xl["Hora"] = xl["Hora"].ffill()
        
        # Filtrar columnas: Solo las que parecen aulas (ej: A-11, SUM, etc.)
        # Excluimos "Dia", "Hora" y nombres de secciones como "Área Básica"
        columnas = [c for c in xl.columns if c not in ["Dia", "Hora"]]
        # Consideramos 'Aula' si tiene un guion o es una palabra corta como SUM o BIBLIO
        aulas_reales = [c for c in columnas if "-" in str(c) or len(str(c)) < 10]
        
        lista = []
        for _, row in xl.iterrows():
            try:
                h_txt = str(row["Hora"]).replace("–", "-").strip()
                h_ini = datetime.strptime(h_txt.split("-")[0].strip(), "%H:%M").time()
                h_fin = datetime.strptime(h_txt.split("-")[1].strip(), "%H:%M").time()
                for a in aulas_reales:
                    val = row[a]
                    ocu = not (pd.isna(val) or str(val).strip() == "")
                    lista.append({
                        "Dia": "".join(filter(str.isalpha, str(row["Dia"]))).upper(),
                        "Hora": h_txt, "H_Ini": h_ini, "H_Fin": h_fin,
                        "AulaNombre": a, "AulaID": normalizar(a),
                        "Detalle": str(val) if ocu else "Libre", "Ocu": ocu
                    })
            except: continue
        df_hor = pd.DataFrame(lista)
    except: pass
    return df_res, df_hor, sorted(aulas_reales)

# ─── LÓGICA PRINCIPAL ────────────────────────────────────────────────────────
df_res, df_hor, lista_aulas = cargar_todo()

st.title("🏫 Control de Aulas UPES")

if not lista_aulas:
    st.error("No se detectaron aulas en el archivo. Revisa los encabezados del Excel.")
else:
    c1, c2 = st.columns(2)
    aula_sel = c1.selectbox("Seleccione el Aula / Instalación", lista_aulas)
    fecha_sel = c2.date_input("Fecha de consulta", value=date.today())

    dias_sem = ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO", "DOMINGO"]
    dia_txt = dias_sem[fecha_sel.weekday()]
    id_buscado = normalizar(aula_sel)

    st.subheader(f"Disponibilidad de {aula_sel} — {fecha_sel.strftime('%d/%m/%Y')}")

    # Filtrar por aula y día
    bloques = df_hor[(df_hor["AulaID"] == id_buscado) & (df_hor["Dia"] == dia_txt)]

    if bloques.empty:
        st.warning(f"No hay clases base para el {dia_txt}. Mostrando solo reservas del formulario.")
        # Mostrar reservas aunque no haya bloques de clase
        res_h = df_res[(df_res['fec'] == fecha_sel) & (df_res['aula'] == id_buscado)]
        for _, r in res_h.iterrows():
            st.markdown(f'<div class="bloque reserva"><span class="time-badge">🟡 {r["ini"]} - {r["fin"]}</span> {r["act"]} ({r["user"]})</div>', unsafe_allow_html=True)
    else:
        for _, row in bloques.iterrows():
            tipo, icono, txt = ("clase", "🔴", row["Detalle"]) if row["Ocu"] else ("libre", "✅", "Libre")
            
            # Cruce con Reservas
            match_r = df_res[(df_res['fec'] == fecha_sel) & (df_res['aula'] == id_buscado)]
            for _, res in match_r.iterrows():
                try:
                    r_ini = datetime.strptime(":".join(res['ini'].split(":")[:2]), "%H:%M").time()
                    r_fin = datetime.strptime(":".join(res['fin'].split(":")[:2]), "%H:%M").time()
                    if row["H_Ini"] < r_fin and r_ini < row["H_Fin"]:
                        tipo, icono, txt = "reserva", "🟡", f"RESERVA: {res['act']} ({res['user']})"
                        break
                except: continue
            
            st.markdown(f'<div class="bloque {tipo}"><span class="time-badge">{icono} {row["Hora"]}</span> {txt}</div>', unsafe_allow_html=True)
