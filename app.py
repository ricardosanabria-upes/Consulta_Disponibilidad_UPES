import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date, time

# ─── CONFIGURACIÓN VISUAL ─────────────────────────────────────────────────────
st.set_page_config(page_title="UPES - Disponibilidad", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    .bloque-item { padding: 10px 18px; border-radius: 10px; margin-bottom: 8px; display: flex; align-items: center; font-size: 0.95rem; border: 1px solid transparent; }
    .bloque-clase { background-color: #fff1f2; border-color: #fecdd3; color: #991b1b; }
    .bloque-libre { background-color: #f0fdf4; border-color: #dcfce7; color: #166534; }
    .bloque-reserva { background-color: #fefce8; border-color: #fef08a; color: #713f12; }
    .time-text { font-weight: 700; margin-right: 8px; min-width: 90px; }
</style>
""", unsafe_allow_html=True)

# ─── FUNCIONES DE LIMPIEZA ────────────────────────────────────────────────────
def normalizar_aula(aula):
    a = str(aula).strip().upper()
    mapeo = {
        "A-21": "A-21 C/ACONDICIONADO",
        "A-22": "A-22 C/ACONDICIONADO",
        "A-34": "A-34 (MESAS DE DIBUJO)"
    }
    for clave, valor in mapeo.items():
        if clave in a: return valor
    return a

# ─── CARGA DE DATOS DESDE EL ENLACE ───────────────────────────────────────────
@st.cache_data(ttl=60)
def cargar_reservas():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
    try:
        response = requests.get(url)
        # Limpieza de la fila "f" inicial del CSV de Google
        content = response.content.decode('utf-8').splitlines()
        valid_lines = [line for line in content if "Marca temporal" in line or "," in line]
        # Encontrar dónde está la cabecera real
        header_idx = 0
        for i, line in enumerate(valid_lines):
            if "Marca temporal" in line:
                header_idx = i
                break
        
        df = pd.read_csv(io.StringIO("\n".join(valid_lines[header_idx:])))
        
        # Mapeo por palabras clave (robusto ante cambios de nombre)
        cols_map = {}
        for c in df.columns:
            low = c.lower()
            if "fecha" in low: cols_map[c] = "fecha"
            elif "instalación" in low or "instalacion" in low: cols_map[c] = "aula"
            elif "inicio" in low: cols_map[c] = "h_ini"
            elif "finalización" in low or "finalizacion" in low or "fin" in low: cols_map[c] = "h_fin"
            elif "actividad" in low: cols_map[c] = "actividad"
            elif "solicitante" in low: cols_map[c] = "nombre"
        
        return df.rename(columns=cols_map)
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
            h_raw = str(row["Hora"]).replace("–", "-").strip()
            try:
                partes = h_raw.split("-")
                h_ini = datetime.strptime(partes[0].strip(), "%H:%M").time()
                h_fin = datetime.strptime(partes[1].strip(), "%H:%M").time()
                for aula in aulas:
                    val = row[aula]
                    ocupado = not (pd.isna(val) or str(val).strip() == "")
                    filas.append({
                        "Dia": str(row["Dia"]).strip(),
                        "Hora": h_raw, "H_Ini": h_ini, "H_Fin": h_fin,
                        "Aula": normalizar_aula(aula),
                        "Detalle": str(val).strip() if ocupado else "Libre",
                        "Ocupada": ocupado
                    })
            except: continue
        return pd.DataFrame(filas)
    except: return None

# ─── LÓGICA PRINCIPAL ─────────────────────────────────────────────────────────
df_h = cargar_horario()
df_r = cargar_reservas()

st.markdown('### 🔍 Consultar disponibilidad')

c1, c2 = st.columns(2)
with c1:
    inst_sel = st.selectbox("Instalación", ["A-11", "A-12", "A-13", "A-14", "A-15", "A-16", "A-21 C/ACONDICIONADO", "A-22 C/ACONDICIONADO", "A-31", "A-32", "A-33", "A-34 (MESAS DE DIBUJO)", "A-35", "A-36", "SUM", "BIBLIOTECA"])
with c2:
    fecha_sel = st.date_input("Fecha", value=date.today())

dia_map = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}

if df_h is not None:
    dia_busc = dia_map.get(fecha_sel.weekday())
    bloques = df_h[(df_h["Aula"] == inst_sel.upper()) & (df_h["Dia"] == dia_busc)]
    
    st.write(f"**{inst_sel} — {fecha_sel.strftime('%d/%m/%Y')}**")

    for _, row in bloques.iterrows():
        tipo, icono, detalle = ("clase", "🔴", row["Detalle"]) if row["Ocupada"] else ("libre", "✅", "Libre")
        
        # VALIDAR RESERVA
        if not row["Ocupada"] and df_r is not None:
            for _, res in df_r.iterrows():
                try:
                    # En tu CSV la fecha es YYYY-MM-DD
                    r_fecha = pd.to_datetime(res["fecha"]).date()
                    r_aula = normalizar_aula(res["aula"])
                    
                    if r_fecha == fecha_sel and inst_sel.upper() in r_aula:
                        # Extraer HH:MM de la reserva
                        r_ini = datetime.strptime(str(res["h_ini"]).strip()[:5], "%H:%M").time()
                        r_fin = datetime.strptime(str(res["h_fin"]).strip()[:5], "%H:%M").time()
                        
                        # Comparación de traslape
                        if row["H_Ini"] < r_fin and r_ini < row["H_Fin"]:
                            tipo, icono = "reserva", "🟡"
                            detalle = f"RESERVA: {res['actividad']} ({res['nombre']})"
                            break
                except: continue

        st.markdown(f"""
            <div class="bloque-item bloque-{tipo}">
                <div style="margin-right:10px">{icono}</div>
                <span class="time-text">{row['Hora']}</span> — {detalle}
            </div>
        """, unsafe_allow_html=True)
