import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date, time, timedelta

# ─── CONFIGURACIÓN DE PÁGINA ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Disponibilidad de Instalaciones — UPES",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── ESTILOS CSS PARA LOGRAR EL LOOK DE LA IMAGEN ────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] { 
        font-family: 'Plus Jakarta Sans', sans-serif; 
    }

    .main-title {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1e1b4b;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    /* Contenedores de bloques estilizados como la imagen */
    .bloque-item {
        padding: 10px 18px;
        border-radius: 10px;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        font-size: 0.95rem;
        border: 1px solid transparent;
        transition: transform 0.1s ease;
    }

    .bloque-clase {
        background-color: #fff1f2;
        border-color: #fecdd3;
        color: #991b1b;
    }

    .bloque-libre {
        background-color: #f0fdf4;
        border-color: #dcfce7;
        color: #166534;
    }

    .icon-container {
        margin-right: 12px;
        display: flex;
        align-items: center;
        font-size: 1.1rem;
    }

    .time-text {
        font-weight: 600;
        margin-right: 8px;
        white-space: nowrap;
    }

    .detail-text {
        font-weight: 400;
    }
</style>
""", unsafe_allow_html=True)

# ─── TU FUNCIÓN DE NORMALIZACIÓN ──────────────────────────────────────────────
def normalizar_aula(aula: str) -> str:
    mapeo = {
        "A-21": "A-21 C/Acondicionado",
        "A-22": "A-22 C/Acondicionado",
        "A-34": "A-34 (Mesas de dibujo)",
    }
    return mapeo.get(aula.strip(), aula.strip())

# ─── CARGA DE DATOS ───────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def cargar_horario():
    url = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"
    try:
        resp = requests.get(url)
        df_raw = pd.read_excel(io.BytesIO(resp.content))
        df_raw["Dia"] = df_raw["Dia"].ffill()
        df_raw["Hora"] = df_raw["Hora"].ffill()
        
        filas = []
        aulas_columnas = [c for c in df_raw.columns if c not in ["Dia", "Hora"]]
        for _, row in df_raw.iterrows():
            dia = str(row["Dia"]).strip()
            hora = str(row["Hora"]).strip()
            for aula in aulas_columnas:
                val = row[aula]
                ocupada = not (pd.isna(val) or str(val).strip() == "")
                filas.append({
                    "Dia": dia, 
                    "Hora": hora, 
                    "Aula": normalizar_aula(aula), # Aquí usamos tu función
                    "Detalle": str(val).strip() if ocupada else "Libre",
                    "Ocupada": ocupada
                })
        return pd.DataFrame(filas)
    except: return None

# ─── INTERFAZ DE USUARIO ──────────────────────────────────────────────────────
df_horario = cargar_horario()

st.markdown('<div class="main-title">🔍 Consultar disponibilidad</div>', unsafe_allow_html=True)

# Selectores superiores
c1, c2 = st.columns(2)
with c1:
    inst_sel = st.selectbox("Instalación", [
        "A-11", "A-12", "A-13", "A-14", "A-15", "A-16",
        "A-21 C/Acondicionado", "A-22 C/Acondicionado",
        "A-31", "A-32", "A-33", "A-34 (Mesas de dibujo)", "A-35", "A-36",
        "A-41", "A-42", "A-43", "A-44", "A-45", "A-46",
        "SUM", "Sala de juntas", "Biblioteca"
    ])
with c2:
    fecha_sel = st.date_input("Fecha", value=date.today())

# Título de resultados
dia_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
dia_excel = {0: "1.Lunes", 1: "2.Martes", 2: "3.Miercoles", 3: "4.Jueves", 4: "5.Viernes", 5: "6.Sabado", 6: "7.Domingo"}

st.write(f"**{inst_sel} — {dia_nombres[fecha_sel.weekday()]} {fecha_sel.strftime('%d/%m/%Y')}**")
st.write("Horario del ciclo:")

# Renderizado de bloques
if df_horario is not None:
    # Filtrado exacto por aula normalizada y día
    dia_busqueda = dia_excel.get(fecha_sel.weekday())
    bloques = df_horario[(df_horario["Aula"] == inst_sel) & (df_horario["Dia"] == dia_busqueda)]
    
    if bloques.empty:
        st.info("No hay clases programadas para este día.")
    else:
        for _, row in bloques.iterrows():
            if row["Ocupada"]:
                tipo_css = "clase"
                icono = "🔴"
            else:
                tipo_css = "libre"
                icono = "✅"
            
            # HTML que genera el estilo de la imagen
            st.markdown(f"""
                <div class="bloque-item bloque-{tipo_css}">
                    <div class="icon-container">{icono}</div>
                    <span class="time-text">{row['Hora']}</span>
                    <span class="detail-text">— {row['Detalle']}</span>
                </div>
            """, unsafe_allow_html=True)
else:
    st.error("Error al cargar datos.")
