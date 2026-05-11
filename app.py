import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="UPES - Control de Disponibilidad", layout="wide")

st.markdown("""
<style>
    .bloque { padding: 12px; border-radius: 8px; margin-bottom: 8px; border: 1px solid #ddd; font-family: sans-serif; }
    .clase { background-color: #f8d7da; color: #721c24; border-left: 6px solid #dc3545; }
    .libre { background-color: #d4edda; color: #155724; border-left: 6px solid #28a745; }
    .reserva { background-color: #fff3cd; color: #856404; border-left: 6px solid #ffc107; font-weight: bold; }
    .time { font-weight: bold; margin-right: 10px; }
</style>
""", unsafe_allow_html=True)

def normalizar(t):
    """Limpia el texto para comparar 'A-11' con 'A11' sin errores."""
    if pd.isna(t): return ""
    return "".join(filter(str.isalnum, str(t))).upper()

@st.cache_data(ttl=5)
def cargar_datos():
    # 1. RESERVAS (GOOGLE SHEETS)
    url_res = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
    try:
        r = requests.get(url_res).text.splitlines()
        idx = next(i for i, line in enumerate(r) if "Marca temporal" in line)
        df = pd.read_csv(io.StringIO("\n".join(r[idx:])))
        df_res = pd.DataFrame({
            'act': df.iloc[:, 4],
            'fec': pd.to_datetime(df.iloc[:, 6], dayfirst=True, errors='coerce').dt.date,
            'aula': df.iloc[:, 7].apply(normalizar),
            'ini': df.iloc[:, 8].astype(str),
            'fin': df.iloc[:, 9].astype(str),
            'user': df.iloc[:, 3]
        })
    except: df_res = pd.DataFrame()

    # 2. HORARIO BASE (GITHUB)
    url_hor = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"
    try:
        resp = requests.get(url_hor)
        xl = pd.read_excel(io.BytesIO(resp.content))
        xl["Dia"] = xl["Dia"].ffill()
        xl["Hora"] = xl["Hora"].ffill()
        aulas_col = [c for c in xl.columns if c not in ["Dia", "Hora"] and "-" in str(c) or len(str(c)) < 10]
        
        lista_h = []
        for _, row in xl.iterrows():
            h_txt = str(row["Hora"]).replace("–", "-").strip()
            h_ini = datetime.strptime(h_txt.split("-")[0].strip(), "%H:%M").time()
            h_fin = datetime.strptime(h_txt.split("-")[1].strip(), "%H:%M").time()
            for a in aulas_col:
                val = row[a]
                ocu = not (pd.isna(val) or str(val).strip() == "")
                lista_h.append({
                    "Dia": "".join(filter(str.isalpha, str(row["Dia"]))).upper(),
                    "Hora": h_txt, "H_Ini": h_ini, "H_Fin": h_fin,
                    "AulaNom": a, "AulaID": normalizar(a),
                    "Detalle": str(val) if ocu else "Libre", "Ocu": ocu
                })
        df_hor = pd.DataFrame(lista_h)
    except: df_hor = pd.DataFrame(); aulas_col = []
    
    return df_res, df_hor, sorted(aulas_col)

df_r, df_h, aulas = cargar_datos()

st.title("🏫 Control de Aulas UPES")

if not aulas:
    st.error("Error al cargar las aulas. Verifica el archivo Excel.")
else:
    c1, c2 = st.columns(2)
    aula_sel = c1.selectbox("Seleccione Aula", aulas)
    fecha_sel = c2.date_input("Fecha", value=date.today())

    dia_buscado = ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO", "DOMINGO"][fecha_sel.weekday()]
    id_aula_buscada = normalizar(aula_sel)

    # FILTRAR BLOQUES DEL HORARIO BASE
    bloques = df_h[(df_h["AulaID"] == id_aula_buscada) & (df_h["Dia"] == dia_buscado)]

    if bloques.empty:
        st.info(f"No hay bloques de clase para {dia_buscado}. Revisando solo reservas...")
    
    # MOSTRAR RESULTADOS
    st.subheader(f"Disponibilidad: {aula_sel} — {fecha_sel.strftime('%d/%m/%Y')}")

    for _, row in bloques.iterrows():
        tipo, icono, texto = ("clase", "🔴", row["Detalle"]) if row["Ocu"] else ("libre", "✅", "Libre")
        
        # --- EL CAMBIO CRÍTICO AQUÍ: Filtro estricto por Aula ---
        # Solo buscamos reservas que coincidan con la fecha Y con el aula seleccionada
        res_validas = df_r[(df_r['fec'] == fecha_sel) & (df_r['aula'] == id_aula_buscada)]
        
        for _, r in res_validas.iterrows():
            try:
                # Normalizar horas de la reserva (HH:MM)
                r_ini = datetime.strptime(":".join(r['ini'].split(":")[:2]), "%H:%M").time()
                r_fin = datetime.strptime(":".join(r['fin'].split(":")[:2]), "%H:%M").time()
                
                # Si el bloque de tiempo choca con la reserva
                if row["H_Ini"] < r_fin and r_ini < row["H_Fin"]:
                    tipo, icono, texto = "reserva", "🟡", f"RESERVA: {r['act']} ({r['user']})"
                    break
            except: continue

        st.markdown(f'<div class="bloque {tipo}"><span class="time">{icono} {row["Hora"]}</span> {texto}</div>', unsafe_allow_html=True)
