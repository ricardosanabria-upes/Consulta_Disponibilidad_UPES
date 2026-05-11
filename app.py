import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date, time, timedelta

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="UPES - Disponibilidad", layout="wide")

# Estilos CSS (Look de la imagen solicitada)
st.markdown("""
<style>
    .bloque-item { padding: 10px 18px; border-radius: 10px; margin-bottom: 8px; display: flex; align-items: center; font-size: 0.95rem; border: 1px solid transparent; }
    .bloque-clase { background-color: #fff1f2; border-color: #fecdd3; color: #991b1b; }
    .bloque-libre { background-color: #f0fdf4; border-color: #dcfce7; color: #166534; }
    .bloque-reserva { background-color: #fefce8; border-color: #fef08a; color: #713f12; }
    .time-text { font-weight: 600; margin-right: 8px; }
</style>
""", unsafe_allow_html=True)

def normalizar_aula(aula: str) -> str:
    mapeo = {"A-21": "A-21 C/Acondicionado", "A-22": "A-22 C/Acondicionado", "A-34": "A-34 (Mesas de dibujo)"}
    return mapeo.get(str(aula).strip(), str(aula).strip())

def hay_traslape(ini1, fin1, ini2, fin2):
    if not all([ini1, fin1, ini2, fin2]): return False
    return ini1 < fin2 and ini2 < fin1

@st.cache_data(ttl=300)
def cargar_reservas():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
    try:
        # Leemos saltando la primera fila si es necesario (header=1)
        df = pd.read_csv(url, header=1)
        df.columns = df.columns.str.strip()
        
        # Mapeo exacto según la imagen enviada
        rename = {
            "Nombre completo del Solicitante": "nombre",
            "Nombre y descripción de la actividad": "actividad",
            "Fecha del evento/actividad:": "fecha",
            "Instalación solicitada (para esto debe haber revisado el documento del paso 1 y respetar las reservas de Clases y eventos)": "instalacion",
            "Hora de inicio (colocarlo en formato de 24 horas):": "hora_inicio",
            "Hora de finalización exacta (colocarlo en formato de 24 horas) :": "hora_fin"
        }
        return df.rename(columns=rename)
    except: return None

@st.cache_data(ttl=3600)
def cargar_horario():
    url = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"
    try:
        resp = requests.get(url)
        df_raw = pd.read_excel(io.BytesIO(resp.content))
        df_raw["Dia"] = df_raw["Dia"].ffill()
        df_raw["Hora"] = df_raw["Hora"].ffill()
        filas = []
        aulas = [c for c in df_raw.columns if c not in ["Dia", "Hora"]]
        for _, row in df_raw.iterrows():
            dia, hora = str(row["Dia"]).strip(), str(row["Hora"]).strip()
            try:
                h_parts = hora.replace("–", "-").split("-")
                h_ini = datetime.strptime(h_parts[0].strip(), "%H:%M").time()
                h_fin = datetime.strptime(h_parts[1].strip(), "%H:%M").time()
            except: h_ini = h_fin = None
            for aula in aulas:
                val = row[aula]
                ocupada = not (pd.isna(val) or str(val).strip() == "")
                filas.append({
                    "Dia": dia, "Hora": hora, "HoraInicio": h_ini, "HoraFin": h_fin,
                    "Aula": normalizar_aula(aula),
                    "Detalle": str(val).strip() if ocupada else "Libre",
                    "Ocupada": ocupada
                })
        return pd.DataFrame(filas)
    except: return None

# --- UI ---
df_horario = cargar_horario()
df_reservas = cargar_reservas()

st.title("🔍 Consultar disponibilidad")

c1, c2 = st.columns(2)
with c1:
    inst_sel = st.selectbox("Instalación", ["A-11", "A-12", "A-13", "A-14", "A-15", "A-16", "A-21 C/Acondicionado", "A-22 C/Acondicionado", "A-31", "A-32", "A-33", "A-34 (Mesas de dibujo)", "A-35", "A-36", "A-41", "A-42", "A-43", "A-44", "A-45", "A-46", "SUM", "Sala de juntas", "Biblioteca"])
with c2:
    fecha_sel = st.date_input("Fecha", value=date.today())

dia_excel_key = {0: "1.Lunes", 1: "2.Martes", 2: "3.Miercoles", 3: "4.Jueves", 4: "5.Viernes", 5: "6.Sabado", 6: "7.Domingo"}

if df_horario is not None:
    dia_busqueda = dia_excel_key.get(fecha_sel.weekday())
    bloques = df_horario[(df_horario["Aula"] == inst_sel) & (df_horario["Dia"] == dia_busqueda)]
    
    st.write(f"**{inst_sel} — {fecha_sel.strftime('%d/%m/%Y')}**")

    for _, row in bloques.iterrows():
        tipo_css = "libre"
        icono = "✅"
        detalle = row["Detalle"]
        
        if row["Ocupada"]:
            tipo_css = "clase"
            icono = "🔴"
        else:
            # --- LÓGICA DE RECONOCIMIENTO DE RESERVA ---
            if df_reservas is not None:
                for _, res in df_reservas.iterrows():
                    try:
                        # Limpieza de fecha: Sheets a veces trae 9/05/2026 o 2026-05-09
                        res_fecha_str = str(res["fecha"]).strip()
                        res_fecha = pd.to_datetime(res_fecha_str, dayfirst=True).date()
                        
                        # Normalizamos nombre de aula de la reserva para comparar
                        res_aula = normalizar_aula(str(res["instalacion"]))
                        
                        if res_fecha == fecha_sel and res_aula == inst_sel:
                            # Limpieza de horas
                            h_ini_res = datetime.strptime(str(res["hora_inicio"]).strip()[:5], "%H:%M").time()
                            h_fin_res = datetime.strptime(str(res["hora_fin"]).strip()[:5], "%H:%M").time()
                            
                            if hay_traslape(row["HoraInicio"], row["HoraFin"], h_ini_res, h_fin_res):
                                tipo_css = "reserva"
                                icono = "🟡"
                                detalle = f"RESERVA: {res['actividad']} ({res['nombre']})"
                                break
                    except: continue

        st.markdown(f"""
            <div class="bloque-item bloque-{tipo_css}">
                <div style="margin-right:10px">{icono}</div>
                <span class="time-text">{row['Hora']}</span>
                <span>— {detalle}</span>
            </div>
        """, unsafe_allow_html=True)
