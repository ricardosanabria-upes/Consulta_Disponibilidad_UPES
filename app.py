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
    initial_sidebar_state="expanded"
)

# ─── ESTILOS CSS (DISEÑO IDÉNTICO A LA IMAGEN) ───────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }

    .main-title {
        font-size: 1.8rem; font-weight: 700; color: #1e1b4b;
        margin-bottom: 20px; display: flex; align-items: center; gap: 10px;
    }

    .bloque-item {
        padding: 10px 18px; border-radius: 10px; margin-bottom: 8px;
        display: flex; align-items: center; font-size: 0.95rem; border: 1px solid transparent;
    }

    .bloque-clase { background-color: #fff1f2; border-color: #fecdd3; color: #991b1b; }
    .bloque-libre { background-color: #f0fdf4; border-color: #dcfce7; color: #166534; }
    .bloque-reserva { background-color: #fefce8; border-color: #fef08a; color: #713f12; }

    .icon-container { margin-right: 12px; display: flex; align-items: center; font-size: 1.1rem; }
    .time-text { font-weight: 600; margin-right: 8px; white-space: nowrap; }
    .detail-text { font-weight: 400; }
</style>
""", unsafe_allow_html=True)

# ─── FUNCIONES DE APOYO ───────────────────────────────────────────────────────
def normalizar_aula(aula: str) -> str:
    mapeo = {
        "A-21": "A-21 C/Acondicionado",
        "A-22": "A-22 C/Acondicionado",
        "A-34": "A-34 (Mesas de dibujo)",
    }
    return mapeo.get(aula.strip(), aula.strip())

def hay_traslape(ini1: time, fin1: time, ini2: time, fin2: time) -> bool:
    if None in [ini1, fin1, ini2, fin2]: return False
    return ini1 < fin2 and ini2 < fin1

# ─── CARGA DE DATOS ───────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def cargar_reservas():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
    try:
        df = pd.read_csv(url, header=1)
        df.columns = df.columns.str.strip()
        # Mapeo flexible de columnas de Google Sheets
        rename = {}
        for col in df.columns:
            c = col.lower()
            if "instalación" in c or "instalacion" in c: rename[col] = "instalacion"
            elif "fecha" in c: rename[col] = "fecha"
            elif "inicio" in c: rename[col] = "hora_inicio"
            elif "finalización" in c or "fin" in c: rename[col] = "hora_fin"
            elif "nombre" in c: rename[col] = "nombre"
            elif "actividad" in c: rename[col] = "actividad"
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

# ─── LÓGICA DE INTERFAZ ───────────────────────────────────────────────────────
df_horario = cargar_horario()
df_reservas = cargar_reservas()

st.markdown('<div class="main-title">🔍 Consultar disponibilidad</div>', unsafe_allow_html=True)

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

dia_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
dia_excel_key = {0: "1.Lunes", 1: "2.Martes", 2: "3.Miercoles", 3: "4.Jueves", 4: "5.Viernes", 5: "6.Sabado", 6: "7.Domingo"}

st.write(f"**{inst_sel} — {dia_nombres[fecha_sel.weekday()]} {fecha_sel.strftime('%d/%m/%Y')}**")
st.write("Horario del ciclo:")

if df_horario is not None:
    dia_busqueda = dia_excel_key.get(fecha_sel.weekday())
    bloques = df_horario[(df_horario["Aula"] == inst_sel) & (df_horario["Dia"] == dia_busqueda)]
    
    for _, row in bloques.iterrows():
        tipo_css = "libre"
        icono = "✅"
        detalle = row["Detalle"]
        
        if row["Ocupada"]:
            tipo_css = "clase"
            icono = "🔴"
        else:
            # VERIFICAR SI HAY RESERVA EN GOOGLE SHEETS PARA ESTE BLOQUE LIBRE
            if df_reservas is not None:
                for _, res in df_reservas.iterrows():
                    try:
                        res_fecha = pd.to_datetime(res["fecha"], dayfirst=True).date()
                        if res_fecha == fecha_sel and str(res["instalacion"]).strip() == inst_sel:
                            res_ini = datetime.strptime(str(res["hora_inicio"])[:5], "%H:%M").time()
                            res_fin = datetime.strptime(str(res["hora_fin"])[:5], "%H:%M").time()
                            
                            if hay_traslape(row["HoraInicio"], row["HoraFin"], res_ini, res_fin):
                                tipo_css = "reserva"
                                icono = "🟡"
                                detalle = f"RESERVADO: {res.get('nombre', 'Evento')} - {res.get('actividad', '')}"
                                break
                    except: continue

        st.markdown(f"""
            <div class="bloque-item bloque-{tipo_css}">
                <div class="icon-container">{icono}</div>
                <span class="time-text">{row['Hora']}</span>
                <span class="detail-text">— {detalle}</span>
            </div>
        """, unsafe_allow_html=True)
else:
    st.error("No se pudo cargar el horario.")

# Sidebar informativo
with st.sidebar:
    st.header("📡 Sincronización")
    if df_reservas is not None: st.success(f"Conectado a Google Sheets ({len(df_reservas)} registros)")
    if st.button("🔄 Refrescar Datos"):
        st.cache_data.clear()
        st.rerun()
