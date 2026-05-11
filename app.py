import streamlit as st
import pandas as pd
import io
from datetime import datetime, date, time, timedelta

# 1. CONFIGURACIÓN Y ESTILOS
st.set_page_config(page_title="UPES Disponibilidad", layout="wide")

st.markdown("""
<style>
    .libre   { background:#f0fdf4; border:1px solid #86efac; border-radius:10px; padding:10px; margin:5px 0; color:#166534; }
    .clase   { background:#fef2f2; border:1px solid #fca5a5; border-radius:10px; padding:10px; margin:5px 0; color:#991b1b; }
    .reserva { background:#fff9db; border:1px solid #fcc419; border-radius:10px; padding:10px; margin:5px 0; color:#856404; }
</style>
""", unsafe_allow_html=True)

# 2. ENLACES Y CONSTANTES
URL_SHEETS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
URL_GITHUB = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"

INSTALACIONES = [
    "A-11", "A-12", "A-13", "A-14", "A-15", "A-16",
    "A-21 C/Acondicionado", "A-22 C/Acondicionado",
    "A-31", "A-32", "A-33", "A-34 (Mesas de dibujo)", "A-35", "A-36",
    "A-41", "A-42", "A-43", "A-44", "A-45", "A-46",
    "SUM", "Sala de juntas", "Pasillos", "Biblioteca"
]

MAPEO_AULAS = {
    "A-25-26": "SUM",
    "A-21": "A-21 C/Acondicionado",
    "A-22": "A-22 C/Acondicionado",
    "A-34": "A-34 (Mesas de dibujo)"
}

# 3. CARGA DE RESERVAS (CORREGIDA)
@st.cache_data(ttl=60)
def cargar_reservas():
    try:
        # Cargamos el archivo completo
        df = pd.read_csv(URL_SHEETS)
        
        # Si la primera fila es basura (título), la saltamos dinámicamente
        if "Fecha" not in "".join(df.columns):
            df = pd.read_csv(URL_SHEETS, skiprows=1)
        
        # Limpiar nombres de columnas
        df.columns = [str(c).strip() for c in df.columns]
        
        # Buscar columnas por palabras clave (para que no falle por nombres largos)
        new_cols = {}
        for c in df.columns:
            c_low = c.lower()
            if "instalación" in c_low or "instalacion" in c_low: new_cols[c] = "aula"
            elif "fecha" in c_low: new_cols[c] = "fecha"
            elif "inicio" in c_low: new_cols[c] = "h_ini"
            elif "finalización" in c_low or "finalizacion" in c_low: new_cols[c] = "h_fin"
            elif "nombre" in c_low: new_cols[c] = "usuario"
        
        df = df.rename(columns=new_cols)
        
        # Limpieza de datos (Aquí estaba el error del 'str')
        if "aula" in df.columns:
            df["aula"] = df["aula"].astype(str).str.strip().replace(MAPEO_AULAS)
            
        # Convertir Fechas y Horas
        df["fecha_dt"] = pd.to_datetime(df["fecha"], dayfirst=True, errors='coerce').dt.date
        df["h_ini_dt"] = pd.to_datetime(df["h_ini"], errors='coerce').dt.time
        df["h_fin_dt"] = pd.to_datetime(df["h_fin"], errors='coerce').dt.time
        
        # Eliminar filas donde la fecha o aula fallaron
        return df.dropna(subset=["aula", "fecha_dt", "h_ini_dt"])
    except Exception as e:
        st.error(f"Error cargando reservaciones: {e}")
        return pd.DataFrame()

# 4. CARGA DE HORARIO (GITHUB)
@st.cache_data(ttl=3600)
def cargar_horario():
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
                # Normalizar guiones largos/cortos
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

# 5. LÓGICA E INTERFAZ
st.title("🏫 Control de Disponibilidad UPES")

df_h = cargar_horario()
df_r = cargar_reservas()

col1, col2 = st.columns(2)
aula_sel = col1.selectbox("Seleccione Aula", INSTALACIONES)
fecha_sel = col2.date_input("Fecha", value=date.today())

# Diccionario para convertir el nombre del día a español (según tu Excel)
DIAS_ES = {0: "1.Lunes", 1: "2.Martes", 2: "3.Miercoles", 3: "4.Jueves", 4: "5.Viernes", 5: "6.Sabado", 6: "7.Domingo"}

if df_h is not None:
    # Bloques de tiempo base para esta aula
    bloques = df_h[df_h["aula"] == aula_sel][["hora_texto", "hi", "hf"]].drop_duplicates().sort_values("hi")
    
    dia_actual = DIAS_ES.get(fecha_sel.weekday())
    
    for _, b in bloques.iterrows():
        estado = "libre"
        detalle = "Disponible"
        
        # ¿Hay clase?
        clase_match = df_h[(df_h["aula"] == aula_sel) & (df_h["dia"] == dia_actual) & (df_h["hi"] == b["hi"]) & (df_h["es_clase"] == True)]
        if not clase_match.empty:
            estado = "clase"
            detalle = clase_match.iloc[0]["detalle"]
        else:
            # ¿Hay reserva?
            if not df_r.empty:
                # Comprobar traslape de tiempo
                res_match = df_r[(df_r["aula"] == aula_sel) & (df_r["fecha_dt"] == fecha_sel)]
                for _, r in res_match.iterrows
