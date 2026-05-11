import streamlit as st
import pandas as pd
import io
from datetime import datetime, date, time, timedelta

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Disponibilidad UPES", layout="wide")

# Estilos CSS
st.markdown("""
<style>
    .libre   { background:#f0fdf4; border:1px solid #86efac; border-radius:10px; padding:10px; margin:5px 0; color:#166534; }
    .clase   { background:#fef2f2; border:1px solid #fca5a5; border-radius:10px; padding:10px; margin:5px 0; color:#991b1b; }
    .reserva { background:#fff9db; border:1px solid #fcc419; border-radius:10px; padding:10px; margin:5px 0; color:#856404; }
</style>
""", unsafe_allow_html=True)

# --- CONSTANTES ---
URL_SHEETS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
URL_GITHUB = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"

# Lista completa de instalaciones
INSTALACIONES = [
    "A-11", "A-12", "A-13", "A-14", "A-15", "A-16",
    "A-21 C/Acondicionado", "A-22 C/Acondicionado",
    "A-31", "A-32", "A-33", "A-34 (Mesas de dibujo)", "A-35", "A-36",
    "A-41", "A-42", "A-43", "A-44", "A-45", "A-46",
    "SUM", "Sala de juntas", "Pasillos", "Biblioteca"
]

# Diccionario de mapeo para asegurar detección entre Sheets y App
MAPEO_AULAS = {
    "A-25-26": "SUM",
    "A-21": "A-21 C/Acondicionado",
    "A-22": "A-22 C/Acondicionado",
    "A-34": "A-34 (Mesas de dibujo)"
}

DIA_SEMANA = {0: "1.Lunes", 1: "2.Martes", 2: "3.Miercoles", 3: "4.Jueves", 4: "5.Viernes", 5: "6.Sabado", 6: "7.Domingo"}

# --- CARGA DE DATOS ---

@st.cache_data(ttl=60)
def cargar_reservas_sheets():
    try:
        # Cargamos saltando la fila de título del Sheet
        df = pd.read_csv(URL_SHEETS, skiprows=1)
        df.columns = df.columns.str.strip()
        
        # Mapeo flexible de columnas por palabras clave
        renombrar = {}
        for c in df.columns:
            c_low = c.lower()
            if "instalación" in c_low or "instalacion" in c_low: renombrar[c] = "aula"
            elif "fecha" in c_low: renombrar[c] = "fecha"
            elif "inicio" in c_low: renombrar[c] = "h_ini"
            elif "finalización" in c_low or "finalizacion" in c_low: renombrar[c] = "h_fin"
            elif "solicitante" in c_low: renombrar[c] = "usuario"
        
        df = df.rename(columns=renombrar)

        # CORRECCIÓN DEL ERROR: Limpieza solo en la columna 'aula'
        if "aula" in df.columns:
            df["aula"] = df["aula"].astype(str).str.strip().replace(MAPEO_AULAS)
        
        # Convertir fechas y horas con formatos robustos
        df["fecha_dt"] = pd.to_datetime(df["fecha"], dayfirst=True, errors='coerce').dt.date
        df["h_ini_dt"] = pd.to_datetime(df["h_ini"], errors='coerce').dt.time
        df["h_fin_dt"] = pd.to_datetime(df["h_fin"], errors='coerce').dt.time
        
        return df.dropna(subset=['aula', 'fecha_dt', 'h_ini_dt'])
    except Exception as e:
        st.error(f"Error en Sheets: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def cargar_horario_github():
    try:
        import requests
        resp = requests.get(URL_GITHUB)
        df_raw = pd.read_excel(io.BytesIO(resp.content))
        df_raw["Dia"] = df_raw["Dia"].ffill()
        df_raw["Hora"] = df_raw["Hora"].ffill()
        
        filas = []
        aulas_cols = [c for c in df_raw.columns if c not in ["Dia", "Hora"]]
        for _, row in df_raw.iterrows():
            dia, hora_str = str(row["Dia"]), str(row["Hora"])
            try:
                partes = hora_str.replace("–", "-").split("-")
                hi = datetime.strptime(partes[0].strip(), "%H:%M").time()
                hf = datetime.strptime(partes[1].strip(), "%H:%M").time()
            except: continue
            
            for a in aulas_cols:
                val = row[a]
                ocupado = not (pd.isna(val) or str(val).strip() == "")
                filas.append({
                    "dia": dia, "hora_texto": hora_str, "hi": hi, "hf": hf,
                    "aula": MAPEO_AULAS.get(a.strip(), a.strip()),
                    "detalle": str(val).strip() if ocupado else "Disponible",
                    "es_clase": ocupado
                })
        return pd.DataFrame(filas)
    except: return None

# --- LÓGICA DE DETECCIÓN ---

def obtener_estado(aula_sel, fecha_sel, hi, hf, df_h, df_r):
    # 1. Prioridad: Horario de clases (GitHub)
    if df_h is not None:
        dia_nombre = DIA_SEMANA.get(fecha_sel.weekday())
        clases = df_h[(df_h["aula"] == aula_sel) & (df_h["dia"] == dia_nombre) & (df_h["es_clase"] == True)]
        for _, c in clases.iterrows():
            if hi < c["hf"] and c["hi"] < hf:
                return "clase", c["detalle"]
    
    # 2. Reservas de Google Sheets
    if not df_r.empty:
        reservas = df_r[(df_r["aula"] == aula_sel) & (df_r["fecha_dt"] == fecha_sel)]
        for _, r in reservas.iterrows():
            if hi < r["h_fin_dt"] and r["h_ini_dt"] < hf:
                return "reserva", f"RESERVADO: {r['usuario']}"
                
    return "libre", "Disponible"

# --- INTERFAZ ---
st.title("🏫 Control de Disponibilidad UPES")

df_h = cargar_horario_github()
df_r = cargar_reservas_sheets()

col1, col2 = st.columns(2)
aula_sel = col1.selectbox("Seleccione Aula", INSTALACIONES)
fecha_sel = col2.date_input("Fecha", value=date.today())

if df_h is not None:
    bloques = df_h[df_h["aula"] == aula_sel][["hora_texto", "hi", "hf"]].drop_duplicates().sort_values("hi")
    for _, b in bloques.iterrows():
        est, det = obtener_estado(aula_sel, fecha_sel, b["hi"], b["hf"], df_h, df_r)
        st.markdown(f"<div class='{est}'><b>{b['hora_texto']}</b> — {det}</div>", unsafe_allow_html=True)

with st.expander("🛠️ Depuración de Reservas"):
    st.dataframe(df_r)
