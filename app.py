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

# MAPEO CRÍTICO: Traduce lo que viene de Sheets a lo que usa el App
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
        # skiprows=1 porque la primera fila es un título general en tu Sheet
        df = pd.read_csv(GOOGLE_SHEET_URL, skiprows=1)
        df.columns = df.columns.str.strip()
        
        # Renombrar columnas por coincidencia parcial (más robusto)
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
            df["instalacion"] = df["instalacion"].astype(str).str.strip()
            df["instalacion"] = df["instalacion"].replace(MAPEO_INSTALACIONES_SHEETS)
        
        # Convertir horas a objetos time (maneja formatos con segundos 08:00:00)
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
                filas.append({
                    "Dia": dia, "Hora": hora, "HoraInicio": h_ini, "HoraFin": h_fin,
                    "Aula": MAPEO_INSTALACIONES_SHEETS.get(aula.strip(), aula.strip()),
                    "Materia": str(val).strip() if ocupada else "", "Ocupada": ocupada
                })
        return pd.DataFrame(filas)
    except: return None

# ─── LÓGICA DE TRASLAPE ───────────────────────────────────────────────────────

def hay_traslape(ini1, fin1, ini2, fin2):
    if None in [ini1, fin1, ini2, fin2]: return False
    return ini1 < fin2 and ini2 < fin1

def get_estado_bloque(instalacion, dia_semana, h_ini, h_fin, df_h, df_r, fecha):
    # 1. Check Horario Ciclo
    if df_h is not None:
        clases = df_h[(df_h["Aula"] == instalacion) & (df_h["Dia"] == dia_semana) & (df_h["Ocupada"] == True)]
        for _, row in clases.iterrows():
            if hay_traslape(h_ini, h_fin, row["HoraInicio"], row["HoraFin"]):
                return "clase", row["Materia"]

    # 2. Check Reservas Sheets
    if df_r is not None and fecha is not None:
        try:
            # Filtro por instalación y fecha
            res = df_r[df_r["instalacion"] == instalacion]
            for _, row in res.iterrows():
                try:
                    fecha_r = pd.to_datetime(row["fecha"], dayfirst=True).date()
                    if fecha_r != fecha: continue
                    if hay_traslape(h_ini, h_fin, row["hora_inicio"], row["hora_fin"]):
                        return "reserva", f"{row['nombre']} — {row['actividad']}"
                except: continue
        except: pass
    return "libre", "Disponible"

def get_bloques_dia(instalacion, fecha, df_h, df_r):
    dia_s = DIA_SEMANA.get(fecha.weekday(), "")
    bloques = []
    
    # Bloques base del horario
    if df_h is not None:
        df_inst = df_h[(df_h["Aula"] == instalacion) & (df_h["Dia"] == dia_s)].sort_values("HoraInicio")
        for _, row in df_inst.iterrows():
            estado, detalle = get_estado_bloque(instalacion, dia_s, row["HoraInicio"], row["HoraFin"], df_h, df_r, fecha)
            bloques.append({"hora": row["Hora"], "tipo": estado, "detalle": detalle, "h_ini": row["HoraInicio"]})
    
    # Agregar reservas de Sheets que no caen en bloques de horario
    if df_r is not None:
        res = df_r[(df_r["instalacion"] == instalacion)]
        for _, row in res.iterrows():
            try:
                fecha_r = pd.to_datetime(row["fecha"], dayfirst=True).date()
                if fecha_r == fecha:
                    # Si no hay un bloque en el horario que ya cubra esta hora exactamente
                    if not any(b["h_ini"] == row["hora_inicio"] for b in bloques):
                        bloques.append({
                            "hora": f"{row['hora_inicio'].strftime('%H:%M')}-{row['hora_fin'].strftime('%H:%M')}",
                            "tipo": "reserva", "detalle": f"{row['nombre']} — {row['actividad']}",
                            "h_ini": row["hora_inicio"]
                        })
            except: continue

    bloques.sort(key=lambda x: x["h_ini"] if x["h_ini"] else time(0,0))
    return bloques

# ─── INTERFAZ STREAMLIT ───────────────────────────────────────────────────────

df_horario = cargar_horario_github()
df_reservas = cargar_reservas_sheets()

# Sidebar
with st.sidebar:
    st.header("📡 Estado")
    if df_horario is not None: st.success("Horario Cargado")
    else: st.error("Error Horario")
    
    if df_reservas is not None:
        st.success(f"Reservas OK ({len(df_reservas)})")
        if st.button("🔄 Refrescar Datos"):
            st.cache_data.clear()
            st.rerun()
    else: st.warning("Sin Reservas")

# Main UI
st.markdown("<h1 class='titulo'>Disponibilidad de Instalaciones</h1>", unsafe_allow_html=True)
st.markdown("<div class='leyenda'><div class='leg-item'><div class='dot-v'></div> Libre</div><div class='leg-item'><div class='dot-
