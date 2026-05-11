import streamlit as st
import pandas as pd
import io
from datetime import datetime, date, time, timedelta

# ─── CONFIGURACIÓN Y ESTILOS ──────────────────────────────────────────────────
st.set_page_config(page_title="UPES - Control de Reservas", layout="wide")

st.markdown("""
<style>
    .libre   { background:#f0fdf4; border:1px solid #86efac; padding:10px; border-radius:10px; color:#166534; margin:5px 0; }
    .clase   { background:#fef2f2; border:1px solid #fca5a5; padding:10px; border-radius:10px; color:#991b1b; margin:5px 0; }
    .reserva { background:#fff9db; border:1px solid #fcc419; padding:10px; border-radius:10px; color:#856404; margin:5px 0; }
</style>
""", unsafe_allow_html=True)

# ─── ENLACES ──────────────────────────────────────────────────────────────────
# Asegúrate de que este CSV sea el de "RESERVAS UPES 2026 (respuestas)"
URL_SHEETS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
URL_GITHUB_HORARIO = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"

# ─── CARGA DE DATOS ───────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def cargar_reservas():
    try:
        df = pd.read_csv(URL_SHEETS)
        # Normalizar nombres de columnas (quitar espacios y tildes)
        df.columns = df.columns.str.strip().str.lower().str.replace('ó','o').str.replace('á','a')
        
        # Mapeo de columnas críticas
        cols = df.columns
        rename_dict = {}
        for c in cols:
            if 'fecha' in c: rename_dict[c] = 'fecha'
            if 'instalacion' in c: rename_dict[c] = 'aula'
            if 'inicio' in c: rename_dict[c] = 'h_ini'
            if 'finalizacion' in c or 'fin' in c: rename_dict[c] = 'h_fin'
        
        df = df.rename(columns=rename_dict)
        
        # Limpieza de datos
        df['aula'] = df['aula'].astype(str).str.strip()
        # Convertir fecha a objeto date de Python para comparar fácil
        df['fecha_dt'] = pd.to_datetime(df['fecha'], dayfirst=True, errors='coerce').dt.date
        
        # Convertir horas
        df['h_ini_dt'] = pd.to_datetime(df['h_ini'], errors='coerce').dt.time
        df['h_fin_dt'] = pd.to_datetime(df['h_fin'], errors='coerce').dt.time
        
        return df.dropna(subset=['fecha_dt', 'aula'])
    except Exception as e:
        st.error(f"Error cargando Reservas: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def cargar_horario():
    # ... (Tu lógica de carga de Excel de GitHub se mantiene igual)
    # Asegúrate de que los nombres de las aulas coincidan exactamente con los de la lista INSTALACIONES
    pass 

# ─── LÓGICA DE VALIDACIÓN (EL CORAZÓN DEL PROBLEMA) ───────────────────────────

def verificar_estado(aula_sel, fecha_sel, hora_inicio_bloque, hora_fin_bloque, df_h, df_r):
    # 1. Verificar CLASES (Horario Fijo)
    # [Aquí va tu lógica actual de df_h que ya funcionaba]
    
    # 2. Verificar RESERVAS (Google Sheets)
    if not df_r.empty:
        # Filtramos por fecha y aula exactas
        reservas_dia = df_r[(df_r['fecha_dt'] == fecha_sel) & (df_r['aula'] == aula_sel)]
        
        for _, res in reservas_dia.iterrows():
            # Validar si las horas se cruzan
            # (Inicio1 < Fin2) AND (Inicio2 < Fin1)
            if (hora_inicio_bloque < res['h_fin_dt']) and (res['h_ini_dt'] < hora_fin_bloque):
                nombre = res.get('nombre completo', 'Reserva')
                return "reserva", f"RESERVADO: {nombre}"
                
    return "libre", "Disponible"

# ─── INTERFAZ ─────────────────────────────────────────────────────────────────

st.title("🏫 Sistema de Disponibilidad UPES")

df_res = cargar_reservas()

# --- BUSCADOR / FILTROS ---
col1, col2 = st.columns(2)
with col1:
    aula = st.selectbox("Seleccione Aula/Instalación", ["A-11", "A-12", "A-13", "A-14", "SUM", "Biblioteca"]) # Añade todas
with col2:
    fecha = st.date_input("Seleccione Fecha", value=date.today())

# --- RENDERIZADO DE BLOQUES ---
# Ejemplo para un bloque de 07:00 a 08:40
h_bloque_ini = time(7, 0)
h_bloque_fin = time(8, 40)

estado, info = verificar_estado(aula, fecha, h_bloque_ini, h_bloque_fin, None, df_res)

st.markdown(f"<div class='{estado}'><b>07:00 - 08:40</b> | {info}</div>", unsafe_allow_html=True)

# --- BOTÓN DE DEBUG (Solo para ti) ---
if st.checkbox("Ver datos crudos de Google Sheets (Debug)"):
    st.write("Registros encontrados en Sheets:", len(df_res))
    st.dataframe(df_res)
