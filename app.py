import streamlit as st
import pandas as pd
import io
from datetime import datetime, date, time, timedelta

# ─── CONFIGURACIÓN DE PÁGINA ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Disponibilidad de Instalaciones — UPES",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    .titulo  { font-size: 2rem; font-weight: 700; color: #1e1b4b; margin-bottom: 0; }
    .sub     { color: #64748b; font-size: 0.95rem; margin-bottom: 1rem; }
    .libre   { background:#f0fdf4; border:1px solid #86efac; border-radius:10px; padding:10px 14px; margin:4px 0; font-size:0.88rem; color:#166534; }
    .clase   { background:#fef2f2; border:1px solid #fca5a5; border-radius:10px; padding:10px 14px; margin:4px 0; font-size:0.88rem; color:#991b1b; }
    .reserva { background:#fefce8; border:1px solid #fde047; border-radius:10px; padding:10px 14px; margin:4px 0; font-size:0.88rem; color:#713f12; }
    .leyenda { display:flex; gap:1.5rem; margin:1rem 0; flex-wrap:wrap; }
    .leg-item{ display:flex; align-items:center; gap:6px; font-size:0.82rem; }
    .dot-v   { width:12px; height:12px; border-radius:50%; background:#86efac; }
    .dot-c   { width:12px; height:12px; border-radius:50%; background:#fca5a5; }
    .dot-r   { width:12px; height:12px; border-radius:50%; background:#fde047; }
</style>
""", unsafe_allow_html=True)

# ─── CONSTANTES Y MAPEOS ──────────────────────────────────────────────────────
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
EXCEL_GITHUB_URL = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"

INSTALACIONES = [
    "A-11", "A-12", "A-13", "A-14", "A-15", "A-16",
    "A-21 C/Acondicionado", "A-22 C/Acondicionado",
    "A-31", "A-32", "A-33", "A-34 (Mesas de dibujo)", "A-35", "A-36",
    "A-41", "A-42", "A-43", "A-44", "A-45", "A-46",
    "SUM", "Sala de juntas", "Pasillos", "Biblioteca",
]

MAPEO_INSTALACIONES_SHEETS = {
    "A-25-26": "SUM",
    "A-21": "A-21 C/Acondicionado",
    "A-22": "A-22 C/Acondicionado",
    "A-34": "A-34 (Mesas de dibujo)",
    "16": "SUM",
    "17": "Sala de juntas"
}

DIA_SEMANA = {0: "1.Lunes", 1: "2.Martes", 2: "3.Miercoles", 3: "4.Jueves", 4: "5.Viernes", 5: "6.Sabado", 6: "7.Domingo"}
DIA_NOMBRE = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}

# ─── FUNCIONES DE CARGA ───────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def cargar_reservas_sheets():
    try:
        df = pd.read_csv(GOOGLE_SHEET_URL, skiprows=1)
        df.columns = df.columns.str.strip()
        
        rename_map = {}
        for col in df.columns:
            c_low = col.lower()
            if "instalación" in c_low or "instalacion" in c_low: rename_map[col] = "instalacion"
            elif "fecha" in c_low: rename_map[col] = "fecha"
            elif "inicio" in c_low: rename_map[col] = "hora_inicio"
            elif "finalización" in c_low or "finalizacion" in c_low: rename_map[col] = "hora_fin"
            elif "nombre completo" in c_low: rename_map[col] = "nombre"
            elif "descripción" in c_low or "descripcion" in c_low: rename_map[col] = "actividad"
        
        df = df.rename(columns=rename_map)

        if "instalacion" in df.columns:
            # CORRECCIÓN: Aplicar .str.strip() a la serie, no al dataframe
            df["instalacion"] = df["instalacion"].fillna("").astype(str).str.strip()
            df["instalacion"] = df["instalacion"].replace(MAPEO_INSTALACIONES_SHEETS)
        
        for h_col in ["hora_inicio", "hora_fin"]:
            if h_col in df.columns:
                df[h_col] = pd.to_datetime(df[h_col].astype(str), errors='coerce').dt.time
                
        return df
    except Exception as e:
        st.error(f"Error en Google Sheets: {e}")
        return None

@st.cache_data(ttl=3600)
def cargar_horario_github():
    try:
        import requests
        resp = requests.get(EXCEL_GITHUB_URL)
        df_raw = pd.read_excel(io.BytesIO(resp.content))
        df_raw.columns = df_raw.columns.str.strip()
        df_raw["Dia"] = df_raw["Dia"].ffill()
        df_raw["Hora"] = df_raw["Hora"].ffill()

        aulas = [c for c in df_raw.columns if c not in ["Dia", "Hora"]]
        filas = []
        for _, row in df_raw.iterrows():
            dia, hora = str(row["Dia"]).strip(), str(row["Hora"]).strip()
            if not dia or dia == "nan" or not hora or hora == "nan": continue
            try:
                partes_h = hora.replace("–", "-").split("-")
                h_ini = datetime.strptime(partes_h[0].strip(), "%H:%M").time()
                h_fin = datetime.strptime(partes_h[1].strip(), "%H:%M").time()
            except: h_ini = h_fin = None

            for aula in aulas:
                val = row[aula]
                ocupada = not (pd.isna(val) or str(val).strip() == "")
                nombre_aula = MAPEO_INSTALACIONES_SHEETS.get(aula.strip(), aula.strip())
                filas.append({
                    "Dia": dia, "Hora": hora, "HoraInicio": h_ini, "HoraFin": h_fin,
                    "Aula": nombre_aula,
                    "Materia": str(val).strip() if ocupada else "", "Ocupada": ocupada
                })
        return pd.DataFrame(filas)
    except: return None

# ─── LÓGICA DE TRASLAPE ───────────────────────────────────────────────────────

def hay_traslape(ini1, fin1, ini2, fin2):
    if None in [ini1, fin1, ini2, fin2]: return False
    return ini1 < fin2 and ini2 < fin1

def get_estado_bloque(instalacion, dia_semana, h_ini, h_fin, df_h, df_r, fecha):
    if df_h is not None:
        clases = df_h[(df_h["Aula"] == instalacion) & (df_h["Dia"] == dia_semana) & (df_h["Ocupada"] == True)]
        for _, row in clases.iterrows():
            if hay_traslape(h_ini, h_fin, row["HoraInicio"], row["HoraFin"]):
                return "clase", row["Materia"]

    if df_r is not None and fecha is not None:
        # Filtro de seguridad para la instalación
        res = df_r[df_r["instalacion"] == instalacion]
        for _, row in res.iterrows():
            try:
                fecha_r = pd.to_datetime(row["fecha"], dayfirst=True).date()
                if fecha_r == fecha:
                    if hay_traslape(h_ini, h_fin, row["hora_inicio"], row["hora_fin"]):
                        nombre = row.get('nombre', 'Anónimo')
                        act = row.get('actividad', 'Sin descripción')
                        return "reserva", f"{nombre} — {act}"
            except: continue
    return "libre", "Disponible"

# ─── INTERFAZ ─────────────────────────────────────────────────────────────────

df_horario = cargar_horario_github()
df_reservas = cargar_reservas_sheets()

with st.sidebar:
    st.header("📡 Estado")
    if df_horario is not None: st.success("Horario Cargado")
    else: st.error("Error Horario")
    if df_reservas is not None: st.success(f"Reservas OK ({len(df_reservas)})")
    if st.button("🔄 Refrescar Datos"):
        st.cache_data.clear()
        st.rerun()

st.markdown("<h1 class='titulo'>Disponibilidad de Instalaciones</h1>", unsafe_allow_html=True)
st.markdown("""
<div class='leyenda'>
    <div class='leg-item'><div class='dot-v'></div> Libre</div>
    <div class='leg-item'><div class='dot-c'></div> Clase</div>
    <div class='leg-item'><div class='dot-r'></div> Reserva</div>
</div>
""", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📅 Por Fecha", "📊 Semanal"])

with tab1:
    c1, c2 = st.columns(2)
    inst = c1.selectbox("Seleccione Instalación", INSTALACIONES)
    fec = c2.date_input("Fecha", value=date.today())
    
    dia_s = DIA_SEMANA.get(fec.weekday(), "")
    
    # Obtener bloques base del horario para esta aula/día
    bloques = []
    if df_horario is not None:
        df_inst = df_horario[(df_horario["Aula"] == inst) & (df_horario["Dia"] == dia_s)].sort_values("HoraInicio")
        for _, row in df_inst.iterrows():
            estado, detalle = get_estado_bloque(inst, dia_s, row["HoraInicio"], row["HoraFin"], df_horario, df_reservas, fec)
            bloques.append({"hora": row["Hora"], "tipo": estado, "detalle": detalle})
    
    if not bloques:
        st.info("No hay bloques de horario registrados para esta instalación en este día.")
    else:
        for b in bloques:
            st.markdown(f"<div class='{b['tipo']}'><b>{b['hora']}</b> — {b['detalle']}</div>", unsafe_allow_html=True)

with tab2:
    inst_s = st.selectbox("Seleccione Instalación", INSTALACIONES, key="s_inst")
    hoy = date.today()
    inicio = hoy - timedelta(days=hoy.weekday())
    dias = [inicio + timedelta(days=i) for i in range(6)]
    
    if df_horario is not None:
        horas_u = df_horario[df_horario["Aula"] == inst_s][["Hora", "HoraInicio", "HoraFin"]].drop_duplicates().sort_values("HoraInicio")
        if not horas_u.empty:
            tabla = []
            for _, h_row in horas_u.iterrows():
                fila = {"Hora": h_row["Hora"]}
                for d in dias:
                    col = f"{DIA_NOMBRE[d.weekday()]} {d.strftime('%d/%m')}"
                    est, _ = get_estado_bloque(inst_s, DIA_SEMANA[d.weekday()], h_row["HoraInicio"], h_row["HoraFin"], df_horario, df_reservas, d)
                    if est == "libre": fila[col] = "✅"
                    elif est == "clase": fila[col] = "🔴 Clase"
                    else: fila[col] = "🟡 Reservado"
                tabla.append(fila)
            st.dataframe(pd.DataFrame(tabla).set_index("Hora"), use_container_width=True)
        else:
            st.info("No hay datos de horario para esta aula.")
