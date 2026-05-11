import streamlit as st
import pandas as pd
import io
from datetime import datetime, date, time, timedelta

# ─── CONFIGURACIÓN DE PÁGINA ──────────────────────────────────────────────────
st.set_page_config(page_title="Disponibilidad UPES", layout="wide")

# Estilos CSS (Tus colores originales)
st.markdown("""
<style>
    .libre   { background:#f0fdf4; border:1px solid #86efac; border-radius:10px; padding:10px; margin:4px 0; color:#166534; }
    .clase   { background:#fef2f2; border:1px solid #fca5a5; border-radius:10px; padding:10px; margin:4px 0; color:#991b1b; }
    .reserva { background:#fefce8; border:1px solid #fde047; border-radius:10px; padding:10px; margin:4px 0; color:#713f12; }
</style>
""", unsafe_allow_html=True)

# ─── CONSTANTES ──────────────────────────────────────────────────────────────
URL_SHEETS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
URL_GITHUB = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"

# TODAS TUS INSTALACIONES RESTAURADAS
INSTALACIONES = [
    "A-11", "A-12", "A-13", "A-14", "A-15", "A-16",
    "A-21 C/Acondicionado", "A-22 C/Acondicionado",
    "A-31", "A-32", "A-33", "A-34 (Mesas de dibujo)", "A-35", "A-36",
    "A-41", "A-42", "A-43", "A-44", "A-45", "A-46",
    "SUM", "Sala de juntas", "Pasillos", "Biblioteca",
]

# MAPEO DE TRADUCCIÓN (Para que Sheets entienda tus nombres)
MAPEO_INSTALACIONES = {
    "A-25-26": "SUM",
    "A-21": "A-21 C/Acondicionado",
    "A-22": "A-22 C/Acondicionado",
    "A-34": "A-34 (Mesas de dibujo)"
}

DIA_SEMANA = {0: "1.Lunes", 1: "2.Martes", 2: "3.Miercoles", 3: "4.Jueves", 4: "5.Viernes", 5: "6.Sabado", 6: "7.Domingo"}

# ─── CARGA DE DATOS ──────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def cargar_reservas_sheets():
    try:
        df = pd.read_csv(URL_SHEETS, skiprows=1) # Saltamos título
        df.columns = df.columns.str.strip()
        
        # Buscamos las columnas por palabras clave para no fallar si cambian ligeramente
        col_map = {}
        for c in df.columns:
            low = c.lower()
            if "instalación" in low or "instalacion" in low: col_map[c] = "aula"
            elif "fecha" in low: col_map[c] = "fecha"
            elif "inicio" in low: col_map[c] = "h_ini"
            elif "finalización" in low or "finalizacion" in low: col_map[c] = "h_fin"
            elif "nombre" in low: col_map[c] = "usuario"
            elif "descripción" in low or "descripcion" in low: col_map[c] = "actividad"
            
        df = df.rename(columns=col_map)
        
        # Limpieza y Mapeo
        if "aula" in df.columns:
            df["aula"] = df["aula"].astype(str).str.strip()
            df["aula"] = df["aula"].replace(MAPEO_INSTALACIONES)
        
        # Formatear fechas y horas
        df["fecha_dt"] = pd.to_datetime(df["fecha"], dayfirst=True, errors='coerce').dt.date
        df["h_ini_dt"] = pd.to_datetime(df["h_ini"], errors='coerce').dt.time
        df["h_fin_dt"] = pd.to_datetime(df["h_fin"], errors='coerce').dt.time
        
        return df
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
        aulas_columnas = [c for c in df_raw.columns if c not in ["Dia", "Hora"]]
        
        for _, row in df_raw.iterrows():
            dia, hora_str = str(row["Dia"]), str(row["Hora"])
            try:
                h_partes = hora_str.replace("–", "-").split("-")
                hi = datetime.strptime(h_partes[0].strip(), "%H:%M").time()
                hf = datetime.strptime(h_partes[1].strip(), "%H:%M").time()
            except: continue
            
            for a in aulas_columnas:
                val = row[a]
                ocupado = not (pd.isna(val) or str(val).strip() == "")
                filas.append({
                    "dia": dia, "hora_texto": hora_str, "hi": hi, "hf": hf,
                    "aula": MAPEO_INSTALACIONES.get(a.strip(), a.strip()),
                    "materia": str(val).strip() if ocupado else "", "es_clase": ocupado
                })
        return pd.DataFrame(filas)
    except: return None

# ─── LÓGICA DE VALIDACIÓN ─────────────────────────────────────────────────────

def get_estado(aula_sel, fecha_sel, hi, hf, df_h, df_r):
    # 1. Prioridad: CLASES (GitHub)
    if df_h is not None:
        dia_nombre = DIA_SEMANA.get(fecha_sel.weekday())
        clase = df_h[(df_h["aula"] == aula_sel) & (df_h["dia"] == dia_nombre) & (df_h["es_clase"] == True)]
        for _, c in clase.iterrows():
            if hi < c["hf"] and c["hi"] < hf:
                return "clase", c["materia"]
    
    # 2. Segunda: RESERVAS (Sheets)
    if not df_r.empty:
        reservas = df_r[(df_r["aula"] == aula_sel) & (df_r["fecha_dt"] == fecha_sel)]
        for _, r in reservas.iterrows():
            if pd.notna(r["h_ini_dt"]) and hi < r["h_fin_dt"] and r["h_ini_dt"] < hf:
                return "reserva", f"Reservado: {r['usuario']} ({r['actividad']})"
                
    return "libre", "Disponible"

# ─── INTERFAZ ─────────────────────────────────────────────────────────────────

st.title("🏫 Sistema de Disponibilidad UPES")

df_h = cargar_horario_github()
df_r = cargar_reservas_sheets()

col1, col2 = st.columns(2)
aula_sel = col1.selectbox("Seleccione Aula", INSTALACIONES)
fecha_sel = col2.date_input("Fecha", value=date.today())

# Mostrar los bloques (Ejemplo de bloques estándar)
if df_h is not None:
    # Obtenemos los bloques de tiempo únicos que existen para esa aula
    bloques = df_h[df_h["aula"] == aula_sel][["hora_texto", "hi", "hf"]].drop_duplicates().sort_values("hi")
    
    for _, b in bloques.iterrows():
        est, det = get_estado(aula_sel, fecha_sel, b["hi"], b["hf"], df_h, df_r)
        st.markdown(f"<div class='{est}'><b>{b['hora_texto']}</b> — {det}</div>", unsafe_allow_html=True)
else:
    st.error("No se pudo cargar el horario base de GitHub.")
