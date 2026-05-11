import streamlit as st
import pandas as pd
import io
from datetime import datetime, date, time, timedelta

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
st.set_page_config(page_title="UPES - Disponibilidad de Aulas", layout="wide")

# Estilos visuales
st.markdown("""
<style>
    .libre   { background:#f0fdf4; border:1px solid #86efac; border-radius:10px; padding:12px; margin:6px 0; color:#166534; }
    .clase   { background:#fef2f2; border:1px solid #fca5a5; border-radius:10px; padding:12px; margin:6px 0; color:#991b1b; }
    .reserva { background:#fff9db; border:1px solid #fcc419; border-radius:10px; padding:12px; margin:6px 0; color:#856404; }
    .debug   { background:#f8f9fa; font-family:monospace; font-size:0.8rem; padding:10px; border-radius:5px; border:1px solid #dee2e6; }
</style>
""", unsafe_allow_html=True)

# ─── CONSTANTES Y MAREOS ──────────────────────────────────────────────────────
URL_SHEETS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
URL_GITHUB = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"

# Lista completa de instalaciones (Nombres estándar del sistema)
INSTALACIONES = [
    "A-11", "A-12", "A-13", "A-14", "A-15", "A-16",
    "A-21 C/Acondicionado", "A-22 C/Acondicionado",
    "A-31", "A-32", "A-33", "A-34 (Mesas de dibujo)", "A-35", "A-36",
    "A-41", "A-42", "A-43", "A-44", "A-45", "A-46",
    "SUM", "Sala de juntas", "Pasillos", "Biblioteca"
]

# Traductor de nombres (Para igualar Excel de GitHub y Google Sheets)
MAPEO_NOMBRES = {
    "A-25-26": "SUM",
    "A-21": "A-21 C/Acondicionado",
    "A-22": "A-22 C/Acondicionado",
    "A-34": "A-34 (Mesas de dibujo)",
    "A-21 C/Acondicionado": "A-21 C/Acondicionado",
    "A-22 C/Acondicionado": "A-22 C/Acondicionado"
}

DIA_SEMANA = {0: "1.Lunes", 1: "2.Martes", 2: "3.Miercoles", 3: "4.Jueves", 4: "5.Viernes", 5: "6.Sabado", 6: "7.Domingo"}

# ─── CARGA DE DATOS ───────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def cargar_reservas_sheets():
    try:
        # Cargamos el CSV saltando la fila de título
        df = pd.read_csv(URL_SHEETS, skiprows=1)
        df.columns = df.columns.str.strip()
        
        # Identificar columnas por palabras clave
        rename_dict = {}
        for c in df.columns:
            low = c.lower()
            if "instalación" in low or "instalacion" in low: rename_dict[c] = "aula"
            elif "fecha" in low: rename_dict[c] = "fecha"
            elif "inicio" in low: rename_dict[c] = "h_ini"
            elif "finalización" in low or "finalizacion" in low: rename_dict[c] = "h_fin"
            elif "solicitante" in low: rename_dict[c] = "usuario"
            elif "actividad" in low: rename_dict[c] = "motivo"
        
        df = df.rename(columns=rename_dict)
        
        # PROCESAMIENTO CRÍTICO
        if "aula" in df.columns:
            # Quitamos espacios y normalizamos según el diccionario
            df["aula"] = df["aula"].astype(str).str.strip().replace(MAPEO_NOMBRES)
            
        # Convertir Fechas (Asegurando formato El Salvador: día/mes/año)
        df["fecha_dt"] = pd.to_datetime(df["fecha"], dayfirst=True, errors='coerce').dt.date
        
        # Convertir Horas (Asegurando formato 24h incluso si vienen con segundos)
        df["h_ini_dt"] = pd.to_datetime(df["h_ini"], errors='coerce').dt.time
        df["h_fin_dt"] = pd.to_datetime(df["h_fin"], errors='coerce').dt.time
        
        return df.dropna(subset=['fecha_dt', 'aula', 'h_ini_dt'])
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
            dia, hora_txt = str(row["Dia"]), str(row["Hora"])
            try:
                h_partes = hora_txt.replace("–", "-").split("-")
                hi = datetime.strptime(h_partes[0].strip(), "%H:%M").time()
                hf = datetime.strptime(h_partes[1].strip(), "%H:%M").time()
            except: continue
            
            for a in aulas_cols:
                val = row[a]
                ocupado = not (pd.isna(val) or str(val).strip() == "")
                filas.append({
                    "dia": dia, "hora_texto": hora_txt, "hi": hi, "hf": hf,
                    "aula": MAPEO_NOMBRES.get(a.strip(), a.strip()),
                    "detalle": str(val).strip() if ocupado else "Disponible",
                    "estado": "clase" if ocupado else "libre"
                })
        return pd.DataFrame(filas)
    except Exception as e:
        st.error(f"Error en GitHub: {e}")
        return None

# ─── LÓGICA DE VALIDACIÓN ─────────────────────────────────────────────────────

def verificar_estado(aula_sel, fecha_sel, hi, hf, df_h, df_r):
    # 1. Chequear Horario de GitHub (Clases)
    if df_h is not None:
        dia_nombre = DIA_SEMANA.get(fecha_sel.weekday())
        match_clase = df_h[(df_h["aula"] == aula_sel) & (df_h["dia"] == dia_nombre)]
        for _, c in match_clase.iterrows():
            # Si hay traslape de horas
            if hi < c["hf"] and c["hi"] < hf:
                if c["estado"] == "clase":
                    return "clase", c["detalle"]
    
    # 2. Chequear Reservas de Google Sheets
    if not df_r.empty:
        # Filtro estricto por aula y fecha
        match_res = df_r[(df_r["aula"] == aula_sel) & (df_r["fecha_dt"] == fecha_sel)]
        for _, r in match_res.iterrows():
            # Si hay traslape con la reserva
            if hi < r["h_fin_dt"] and r["h_ini_dt"] < hf:
                return "reserva", f"RESERVADO: {r['usuario']} - {r['motivo']}"
                
    return "libre", "Disponible"

# ─── INTERFAZ DE USUARIO ──────────────────────────────────────────────────────

st.title("🏫 Control de Disponibilidad - UPES")

df_h = cargar_horario_github()
df_r = cargar_reservas_sheets()

with st.sidebar:
    st.header("⚙️ Estado de Datos")
    if not df_r.empty: st.success(f"Reservas: {len(df_r)} cargadas")
    if df_h is not None: st.success("Horario GitHub: OK")
    if st.button("🔄 Forzar Actualización"):
        st.cache_data.clear()
        st.rerun()

col1, col2 = st.columns(2)
aula_sel = col1.selectbox("Seleccione Instalación", INSTALACIONES)
fecha_sel = col2.date_input("Seleccione Fecha", value=date.today())

st.divider()

if df_h is not None:
    # Obtenemos los bloques de tiempo estándar para esta aula
    bloques = df_h[df_h["aula"] == aula_sel][["hora_texto", "hi", "hf"]].drop_duplicates().sort_values("hi")
    
    if bloques.empty:
        st.warning("No se encontraron bloques de tiempo para esta aula en el horario base.")
    else:
        for _, b in bloques.iterrows():
            est, det = verificar_estado(aula_sel, fecha_sel, b["hi"], b["hf"], df_h, df_r)
            st.markdown(f"<div class='{est}'><b>{b['hora_texto']}</b> — {det}</div>", unsafe_allow_html=True)
else:
    st.error("Error crítico: No se pudo cargar el horario base.")

# Modo Debug para el administrador
with st.expander("🛠️ Depuración de Datos (Solo Admin)"):
    st.write("Datos procesados de Google Sheets:")
    st.dataframe(df_r)
