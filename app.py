import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="UPES - Disponibilidad", layout="wide")

st.markdown("""
<style>
    .bloque-item { padding: 12px; border-radius: 8px; margin-bottom: 5px; display: flex; align-items: center; border: 1px solid #ddd; }
    .bloque-clase { background-color: #ffebee; color: #b71c1c; border-left: 5px solid #b71c1c; }
    .bloque-libre { background-color: #e8f5e9; color: #1b5e20; border-left: 5px solid #1b5e20; }
    .bloque-reserva { background-color: #fff9c4; color: #827717; border-left: 5px solid #fbc02d; }
    .time-text { font-weight: bold; margin-right: 15px; width: 100px; }
</style>
""", unsafe_allow_html=True)

def limpiar_id(t):
    """Convierte 'A-21 C/ACOND.' en 'A21CACOND' para que siempre coincidan."""
    if pd.isna(t): return ""
    return "".join(filter(str.isalnum, str(t))).upper()

@st.cache_data(ttl=10)
def cargar_reservas():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
    try:
        response = requests.get(url)
        # Limpieza de la 'f' inicial de Google Sheets
        content = response.text.splitlines()
        start_row = 0
        for i, line in enumerate(content):
            if "Marca temporal" in line:
                start_row = i
                break
        df = pd.read_csv(io.StringIO("\n".join(content[start_row:])))
        
        # Mapeo por POSICIÓN (Col 3: Nombre, Col 4: Actividad, Col 6: Fecha, Col 7: Aula, Col 8: Inicio, Col 9: Fin)
        res = pd.DataFrame()
        res['nombre'] = df.iloc[:, 3]
        res['actividad'] = df.iloc[:, 4]
        res['fecha'] = df.iloc[:, 6]
        res['aula_id'] = df.iloc[:, 7].apply(limpiar_id)
        res['h_ini'] = df.iloc[:, 8]
        res['h_fin'] = df.iloc[:, 9]
        return res
    except: return None

@st.cache_data(ttl=3600)
def cargar_horario():
    url = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"
    try:
        resp = requests.get(url)
        df = pd.read_excel(io.BytesIO(resp.content))
        df["Dia"] = df["Dia"].ffill()
        df["Hora"] = df["Hora"].ffill()
        
        filas = []
        aulas = [c for c in df.columns if c not in ["Dia", "Hora"]]
        for _, row in df.iterrows():
            h_str = str(row["Hora"]).replace("–", "-").strip()
            try:
                h_ini = datetime.strptime(h_str.split("-")[0].strip(), "%H:%M").time()
                h_fin = datetime.strptime(h_str.split("-")[1].strip(), "%H:%M").time()
                for a in aulas:
                    val = row[a]
                    ocupado = not (pd.isna(val) or str(val).strip() == "")
                    filas.append({
                        "Dia": str(row["Dia"]).strip(),
                        "Hora": h_str, "H_Ini": h_ini, "H_Fin": h_fin,
                        "AulaID": limpiar_id(a),
                        "Detalle": str(val).strip() if ocupado else "Libre",
                        "Ocupada": ocupado
                    })
            except: continue
        return pd.DataFrame(filas)
    except: return None

# --- UI ---
df_h = cargar_horario()
df_r = cargar_reservas()

st.title("🔍 Disponibilidad UPES")

aula_sel = st.selectbox("Seleccione Instalación", ["A-11", "A-12", "A-13", "A-14", "A-15", "A-16", "A-21 C/ACONDICIONADO", "A-22 C/ACONDICIONADO", "SUM", "BIBLIOTECA"])
fecha_sel = st.date_input("Fecha", value=date.today())

dias = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}

if df_h is not None:
    id_buscado = limpiar_id(aula_sel)
    dia_buscado = dias[fecha_sel.weekday()]
    
    bloques = df_h[(df_h["AulaID"] == id_buscado) & (df_h["Dia"] == dia_buscado)]
    
    for _, row in bloques.iterrows():
        tipo, icono, detalle = ("clase", "🔴", row["Detalle"]) if row["Ocupada"] else ("libre", "✅", "Libre")
        
        # CRUCE CON RESERVAS
        if not row["Ocupada"] and df_r is not None:
            for _, res in df_r.iterrows():
                try:
                    r_fecha = pd.to_datetime(res['fecha']).date()
                    if r_fecha == fecha_sel and res['aula_id'] == id_buscado:
                        # Limpieza de segundos (08:00:00 -> 08:00)
                        h_res_ini = datetime.strptime(str(res['h_ini'])[:5], "%H:%M").time()
                        h_res_fin = datetime.strptime(str(res['h_fin'])[:5], "%H:%M").time()
                        
                        if row["H_Ini"] < h_res_fin and h_res_ini < row["H_Fin"]:
                            tipo, icono = "reserva", "🟡"
                            detalle = f"RESERVA: {res['actividad']} ({res['nombre']})"
                            break
                except: continue

        st.markdown(f'<div class="bloque-item bloque-{tipo}"><span class="time-text">{icono} {row["Hora"]}</span>{detalle}</div>', unsafe_allow_html=True)
