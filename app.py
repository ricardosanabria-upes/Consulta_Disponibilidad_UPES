import streamlit as st
import pandas as pd
import io
from datetime import datetime, date

# 1. Configuración de Interfaz
st.set_page_config(page_title="Control UPES", layout="wide")

# CSS en bloque único para evitar errores de sintaxis al copiar
st.markdown("""
<style>
    .bloque { padding:12px; margin:6px 0; border-radius:10px; border:1px solid #d1d5db; font-family: sans-serif; }
    .libre { background-color: #f0fdf4; color: #166534; border-color: #bbf7d0; }
    .clase { background-color: #fef2f2; color: #991b1b; border-color: #fecaca; }
    .reserva { background-color: #fff9db; color: #856404; border-color: #fef08a; }
</style>
""", unsafe_allow_html=True)

URL_SHEETS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
URL_GITHUB = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"

# 2. Carga de Reservas - IDENTIFICACIÓN POR POSICIÓN (No por nombre)
@st.cache_data(ttl=60)
def cargar_reservas():
    try:
        # Cargamos saltando la fila de título 'RESERVAS UPES 2026'
        df = pd.read_csv(URL_SHEETS, skiprows=1)
        
        # Usamos los índices de las columnas según tu captura de pantalla:
        # Columna 3: Nombre del solicitante
        # Columna 6: Fecha
        # Columna 7: Instalación (Aula)
        # Columna 8: Hora Inicio
        # Columna 9: Hora Finalización
        
        df_limpio = pd.DataFrame()
        df_limpio['user'] = df.iloc[:, 3].astype(str)
        df_limpio['fecha_raw'] = df.iloc[:, 6].astype(str)
        df_limpio['aula'] = df.iloc[:, 7].astype(str).str.strip()
        df_limpio['h_ini_raw'] = df.iloc[:, 8].astype(str)
        df_limpio['h_fin_raw'] = df.iloc[:, 9].astype(str)

        # Normalización de nombres de aula para match exacto
        df_limpio['aula'] = df_limpio['aula'].replace({
            "A-21": "A-21 C/Acondicionado",
            "A-22": "A-22 C/Acondicionado",
            "A-34": "A-34 (Mesas de dibujo)"
        })

        # Conversión de tiempos
        df_limpio['fecha_dt'] = pd.to_datetime(df_limpio['fecha_raw'], dayfirst=True, errors='coerce').dt.date
        df_limpio['hi_dt'] = pd.to_datetime(df_limpio['h_ini_raw'], errors='coerce').dt.time
        df_limpio['hf_dt'] = pd.to_datetime(df_limpio['h_fin_raw'], errors='coerce').dt.time
        
        return df_limpio.dropna(subset=['fecha_dt', 'hi_dt'])
    except Exception as e:
        st.error(f"Error técnico en Sheets: {e}")
        return pd.DataFrame()

# 3. Carga de Horario (GitHub)
@st.cache_data(ttl=3600)
def cargar_horario():
    try:
        import requests
        r = requests.get(URL_GITHUB)
        df_raw = pd.read_excel(io.BytesIO(r.content))
        df_raw["Dia"] = df_raw["Dia"].ffill()
        df_raw["Hora"] = df_raw["Hora"].ffill()
        
        lista = []
        aulas_cols = [c for c in df_raw.columns if c not in ["Dia", "Hora"]]
        for _, row in df_raw.iterrows():
            try:
                h_txt = str(row["Hora"]).replace("–", "-")
                hi = datetime.strptime(h_txt.split("-")[0].strip(), "%H:%M").time()
                hf = datetime.strptime(h_txt.split("-")[1].strip(), "%H:%M").time()
                for a in aulas_cols:
                    val = str(row[a]).strip()
                    es_clase = val != "" and val.lower() != "nan"
                    lista.append({
                        "dia": str(row["Dia"]), "hora_t": h_txt, "hi": hi, "hf": hf,
                        "aula": a.strip(), "detalle": val if es_clase else "Disponible", 
                        "tipo": "clase" if es_clase else "libre"
                    })
            except: continue
        return pd.DataFrame(lista)
    except: return None

# 4. Interfaz Principal
st.title("🏫 Control de Instalaciones UPES")

df_h = cargar_horario()
df_r = cargar_reservas()

# Selectores automáticos basados en el horario cargado
if df_h is not None:
    aulas_disponibles = sorted(df_h["aula"].unique())
    col1, col2 = st.columns(2)
    aula_sel = col1.selectbox("Seleccione Aula", aulas_disponibles)
    fecha_sel = col2.date_input("Seleccione Fecha", value=date.today())

    # Mapeo de día para el horario de clases
    dias_map = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}
    dia_buscado = dias_map.get(fecha_sel.weekday())

    # Generar bloques horarios para el aula seleccionada
    bloques = df_h[df_h["aula"] == aula_sel].drop_duplicates("hora_t").sort_values("hi")

    for _, b in bloques.iterrows():
        estado, info = "libre", "Disponible"

        # Prioridad 1: Clase fija
        match_clase = df_h[(df_h["aula"] == aula_sel) & (df_h["dia"] == dia_buscado) & (df_h["hora_t"] == b["hora_t"]) & (df_h["tipo"] == "clase")]
        
        if not match_clase.empty:
            estado, info = "clase", match_clase
