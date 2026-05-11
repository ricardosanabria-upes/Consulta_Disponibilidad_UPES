import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

# --- CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="UPES - Disponibilidad", layout="wide")

st.markdown("""
<style>
    .bloque-item { padding: 15px; border-radius: 10px; margin-bottom: 8px; display: flex; align-items: center; border: 1px solid #ddd; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .bloque-clase { background-color: #ffebee; color: #b71c1c; border-left: 6px solid #b71c1c; }
    .bloque-libre { background-color: #e8f5e9; color: #1b5e20; border-left: 6px solid #1b5e20; }
    .bloque-reserva { background-color: #fff9c4; color: #827717; border-left: 6px solid #fbc02d; }
    .time-text { font-weight: bold; margin-right: 15px; width: 110px; font-size: 1rem; }
</style>
""", unsafe_allow_html=True)

def limpiar_id(texto):
    """Convierte 'A-21 C/ACONDICIONADO' en 'A21CACONDICIONADO' para comparar sin fallos."""
    if pd.isna(texto): return ""
    return "".join(filter(str.isalnum, str(texto))).upper()

@st.cache_data(ttl=30)
def cargar_reservas():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
    try:
        response = requests.get(url)
        content = response.content.decode('utf-8').splitlines()
        # Buscamos la fila de cabecera real
        start_idx = 0
        for i, line in enumerate(content):
            if "Marca temporal" in line:
                start_idx = i
                break
        df = pd.read_csv(io.StringIO("\n".join(content[start_idx:])))
        
        # Extraemos las columnas por su posición física (índice), ya que los nombres tienen saltos de línea
        res = pd.DataFrame()
        res['nombre'] = df.iloc[:, 3]        # Columna D
        res['actividad'] = df.iloc[:, 4]     # Columna E
        res['fecha'] = df.iloc[:, 6]         # Columna G
        res['aula_id'] = df.iloc[:, 7].apply(limpiar_id) # Columna H
        res['h_ini'] = df.iloc[:, 8]         # Columna I
        res['h_fin'] = df.iloc[:, 9]         # Columna J
        return res
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
        for _, row in df_raw.iterrows():
            h_str = str(row["Hora"]).replace("–", "-").strip()
            try:
                # Extraer horas de inicio y fin del bloque de clase
                h_ini = datetime.strptime(h_str.split("-")[0].strip(), "%H:%M").time()
                h_fin = datetime.strptime(h_str.split("-")[1].strip(), "%H:%M").time()
                for col in [c for c in df_raw.columns if c not in ["Dia", "Hora"]]:
                    val = row[col]
                    ocupado = not (pd.isna(val) or str(val).strip() == "")
                    filas.append({
                        "Dia": str(row["Dia"]).strip(),
                        "Hora": h_str, "H_Ini": h_ini, "H_Fin": h_fin,
                        "AulaID": limpiar_id(col),
                        "Detalle": str(val).strip() if ocupado else "Libre",
                        "Ocupada": ocupado
                    })
            except: continue
        return pd.DataFrame(filas)
    except: return None

# --- APP PRINCIPAL ---
df_h = cargar_horario()
df_r = cargar_reservas()

st.title("🔍 Disponibilidad de Instalaciones UPES")

aula_sel = st.selectbox("Seleccione la Instalación", ["A-11", "A-12", "A-13", "A-14", "A-15", "A-16", "A-21 C/ACONDICIONADO", "A-22 C/ACONDICIONADO", "A-31", "A-32", "A-33", "A-34", "SUM", "BIBLIOTECA"])
fecha_sel = st.date_input("Fecha de consulta", value=date.today())

dias_map = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}

if df_h is not None:
    id_buscado = limpiar_id(aula_sel)
    dia_buscado = dias_map[fecha_sel.weekday()]
    
    bloques = df_h[(df_h["AulaID"] == id_buscado) & (df_h["Dia"] == dia_buscado)]
    
    st.subheader(f"Horario para {aula_sel} — {fecha_sel.strftime('%d/%m/%Y')}")

    for _, row in bloques.iterrows():
        tipo, icono, detalle = ("clase", "🔴", row["Detalle"]) if row["Ocupada"] else ("libre", "✅", "Libre")
        
        # VALIDACIÓN CONTRA RESERVAS
        if not row["Ocupada"] and df_r is not None:
            for _, res in df_r.iterrows():
                try:
                    # 1. Comparar Fecha
                    r_fecha = pd.to_datetime(res['fecha']).date()
                    # 2. Comparar Aula (ID limpio)
                    if r_fecha == fecha_sel and res['aula_id'] == id_buscado:
                        # 3. Comparar Horas (limpiando segundos :00:00)
                        r_ini = datetime.strptime(str(res['h_ini'])[:5], "%H:%M").time()
                        r_fin = datetime.strptime(str(res['h_fin'])[:5], "%H:%M").time()
                        
                        if row["H_Ini"] < r_fin and r_ini < row["H_Fin"]:
                            tipo, icono = "reserva", "🟡"
                            detalle = f"RESERVA: {res['actividad']} ({res['nombre']})"
                            break
                except: continue

        st.markdown(f"""
            <div class="bloque-item bloque-{tipo}">
                <div class="time-text">{icono} {row['Hora']}</div>
                <div>{detalle}</div>
            </div>
        """, unsafe_allow_html=True)
