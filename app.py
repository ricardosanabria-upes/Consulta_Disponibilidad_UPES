import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date, time

# ─── CONFIGURACIÓN DE PÁGINA ──────────────────────────────────────────────────
st.set_page_config(page_title="UPES - Disponibilidad", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    .bloque-item { padding: 10px 18px; border-radius: 10px; margin-bottom: 8px; display: flex; align-items: center; font-size: 0.95rem; border: 1px solid transparent; }
    .bloque-clase { background-color: #fff1f2; border-color: #fecdd3; color: #991b1b; }
    .bloque-libre { background-color: #f0fdf4; border-color: #dcfce7; color: #166534; }
    .bloque-reserva { background-color: #fefce8; border-color: #fef08a; color: #713f12; }
    .time-text { font-weight: 600; margin-right: 8px; }
</style>
""", unsafe_allow_html=True)

# ─── FUNCIONES DE LIMPIEZA ────────────────────────────────────────────────────
def normalizar_aula(aula):
    a = str(aula).strip().upper()
    if "A-21" in a: return "A-21 C/ACONDICIONADO"
    if "A-22" in a: return "A-22 C/ACONDICIONADO"
    if "A-34" in a: return "A-34 (MESAS DE DIBUJO)"
    return a

# ─── CARGA DE DATOS (URL DE GOOGLE SHEETS) ────────────────────────────────────
@st.cache_data(ttl=60)
def cargar_reservas():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
    try:
        # Cargamos todo el CSV
        response = requests.get(url)
        content = response.content.decode('utf-8')
        
        # Saltamos la fila de basura inicial (la 'f') buscando la fila que contiene 'Marca temporal'
        lines = content.splitlines()
        start_line = 0
        for i, line in enumerate(lines):
            if "Marca temporal" in line:
                start_line = i
                break
        
        df = pd.read_csv(io.StringIO("\n".join(lines[start_line:])))
        df.columns = [c.strip() for c in df.columns]
        
        # BUSCADOR FLEXIBLE DE COLUMNAS
        mapping = {}
        for col in df.columns:
            c_low = col.lower()
            if "fecha" in c_low: mapping[col] = "fecha"
            elif "instalación" in c_low or "instalacion" in c_low: mapping[col] = "aula"
            elif "inicio" in c_low: mapping[col] = "h_ini"
            elif "finalización" in c_low or "finalizacion" in c_low or "fin" in c_low: mapping[col] = "h_fin"
            elif "actividad" in c_low: mapping[col] = "actividad"
            elif "nombre" in c_low: mapping[col] = "nombre"
        
        return df.rename(columns=mapping)
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return None

@st.cache_data(ttl=3600)
def cargar_horario():
    url = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"
    try:
        resp = requests.get(url)
        df_raw = pd.read_excel(io.BytesIO(resp.content))
        df_raw["Dia"] = df_raw["Dia"].ffill()
        df_raw["Hora"] = df_raw["Hora"].ffill()
        
        filas = []
        aulas_cols = [c for c in df_raw.columns if c not in ["Dia", "Hora"]]
        for _, row in df_raw.iterrows():
            h_str = str(row["Hora"]).replace("–", "-")
            try:
                h_ini = datetime.strptime(h_str.split("-")[0].strip(), "%H:%M").time()
                h_fin = datetime.strptime(h_str.split("-")[1].strip(), "%H:%M").time()
            except: continue
            
            for aula in aulas_cols:
                val = row[aula]
                ocupada = not (pd.isna(val) or str(val).strip() == "")
                filas.append({
                    "Dia": str(row["Dia"]).strip(),
                    "Hora": h_str, "H_Ini": h_ini, "H_Fin": h_fin,
                    "Aula": normalizar_aula(aula),
                    "Detalle": str(val).strip() if ocupada else "Libre",
                    "Ocupada": ocupada
                })
        return pd.DataFrame(filas)
    except: return None

# ─── LOGICA PRINCIPAL ─────────────────────────────────────────────────────────
df_h = cargar_horario()
df_r = cargar_reservas()

st.markdown('### 🔍 Consultar disponibilidad')

c1, c2 = st.columns(2)
with c1:
    lista_aulas = ["A-11", "A-12", "A-13", "A-14", "A-15", "A-16", "A-21 C/ACONDICIONADO", "A-22 C/ACONDICIONADO", "A-31", "A-32", "A-33", "A-34 (MESAS DE DIBUJO)", "SUM", "BIBLIOTECA"]
    inst_sel = st.selectbox("Instalación", lista_aulas)
with c2:
    fecha_sel = st.date_input("Fecha", value=date.today())

dia_map = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}

if df_h is not None:
    # Filtrar horario del Excel
    bloques = df_h[(df_h["Aula"] == inst_sel.upper()) & (df_h["Dia"] == dia_map[fecha_sel.weekday()])]
    st.write(f"**{inst_sel} — {fecha_sel.strftime('%d/%m/%Y')}**")

    for _, row in bloques.iterrows():
        tipo, icono, detalle = ("clase", "🔴", row["Detalle"]) if row["Ocupada"] else ("libre", "✅", "Libre")
        
        # COMPROBAR CONTRA RESERVAS DEL ENLACE
        if not row["Ocupada"] and df_r is not None:
            for _, res in df_r.iterrows():
                try:
                    # Normalizar fecha de la reserva (soporta YYYY-MM-DD y DD/MM/YYYY)
                    res_f = pd.to_datetime(res["fecha"]).date()
                    res_a = normalizar_aula(res["aula"])
                    
                    if res_f == fecha_sel and inst_sel.upper() in res_a:
                        r_ini = datetime.strptime(str(res["h_ini"]).strip()[:5], "%H:%M").time()
                        r_fin = datetime.strptime(str(res["h_fin"]).strip()[:5], "%H:%M").time()
                        
                        # Si hay cruce de horas
                        if row["H_Ini"] < r_fin and r_ini < row["H_Fin"]:
                            tipo, icono = "reserva", "🟡"
                            detalle = f"RESERVA: {res['actividad']} ({res['nombre']})"
                            break
                except: continue

        st.markdown(f"""
            <div class="bloque-item bloque-{tipo}">
                <div style="margin-right:10px">{icono}</div>
                <span class="time-text">{row['Hora']}</span> — {detalle}
            </div>
        """, unsafe_allow_html=True)
