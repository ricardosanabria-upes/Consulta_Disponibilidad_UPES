import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="UPES - Disponibilidad", layout="wide")

# Estilo visual
st.markdown("""
<style>
    .bloque-item { padding: 12px; border-radius: 8px; margin-bottom: 5px; display: flex; align-items: center; border: 1px solid #ddd; }
    .bloque-clase { background-color: #ffebee; color: #b71c1c; }
    .bloque-libre { background-color: #e8f5e9; color: #1b5e20; }
    .bloque-reserva { background-color: #fff9c4; color: #827717; border-color: #fbc02d; }
    .time-text { font-weight: bold; margin-right: 15px; width: 100px; }
</style>
""", unsafe_allow_html=True)

def limpiar_aula(txt):
    """Elimina todo lo que no sea letra o número para comparar A-11 con A11"""
    if pd.isna(txt): return ""
    return "".join(filter(str.isalnum, str(txt))).upper()

@st.cache_data(ttl=30)
def cargar_reservas():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
    try:
        response = requests.get(url)
        # Forzar la lectura saltando cualquier basura inicial hasta encontrar "Marca temporal"
        lines = response.content.decode('utf-8').splitlines()
        for i, line in enumerate(lines):
            if "Marca temporal" in line:
                df = pd.read_csv(io.StringIO("\n".join(lines[i:])))
                break
        
        # Limpieza agresiva de nombres de columnas
        df.columns = [c.replace('\n', ' ').strip() for c in df.columns]
        
        # Mapeo manual por posición si los nombres fallan (basado en tu CSV)
        # 3: Nombre, 4: Actividad, 6: Fecha, 7: Aula, 8: Inicio, 9: Fin
        df_new = pd.DataFrame()
        df_new['nombre'] = df.iloc[:, 3]
        df_new['actividad'] = df.iloc[:, 4]
        df_new['fecha'] = df.iloc[:, 6]
        df_new['aula'] = df.iloc[:, 7]
        df_new['h_ini'] = df.iloc[:, 8]
        df_new['h_fin'] = df.iloc[:, 9]
        
        return df_new
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
                h_ini = datetime.strptime(h_str.split("-")[0].strip(), "%H:%M").time()
                h_fin = datetime.strptime(h_str.split("-")[1].strip(), "%H:%M").time()
                for aula in [c for c in df_raw.columns if c not in ["Dia", "Hora"]]:
                    val = row[aula]
                    ocupado = not (pd.isna(val) or str(val).strip() == "")
                    filas.append({
                        "Dia": str(row["Dia"]).strip(),
                        "Hora": h_str, "H_Ini": h_ini, "H_Fin": h_fin,
                        "Aula": str(aula).strip().upper(),
                        "AulaID": limpiar_aula(aula),
                        "Detalle": str(val).strip() if ocupado else "Libre",
                        "Ocupada": ocupado
                    })
            except: continue
        return pd.DataFrame(filas)
    except: return None

# --- EJECUCIÓN ---
df_h = cargar_horario()
df_r = cargar_reservas()

st.title("🔍 Disponibilidad UPES")

aula_sel = st.selectbox("Instalación", ["A-11", "A-12", "A-13", "A-14", "A-15", "A-16", "A-21 C/ACONDICIONADO", "A-22 C/ACONDICIONADO", "SUM", "BIBLIOTECA"])
fecha_sel = st.date_input("Fecha", value=date.today())

dias = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}

if df_h is not None:
    bloques = df_h[(df_h["AulaID"] == limpiar_aula(aula_sel)) & (df_h["Dia"] == dias[fecha_sel.weekday()])]
    
    for _, row in bloques.iterrows():
        tipo, icono, detalle = ("clase", "🔴", row["Detalle"]) if row["Ocupada"] else ("libre", "✅", "Libre")
        
        # VALIDAR RESERVA (Comparación Flexible)
        if not row["Ocupada"] and df_r is not None:
            for _, res in df_r.iterrows():
                try:
                    # Fecha: Soporta 2026-05-11 y 11/05/2026
                    r_fecha = pd.to_datetime(res['fecha']).date()
                    # Aula: Compara "A11" con "A11" (sin guiones ni espacios)
                    if r_fecha == fecha_sel and limpiar_aula(res['aula']) == limpiar_aula(aula_sel):
                        # Hora: Corta los segundos (08:00:00 -> 08:00)
                        r_ini = datetime.strptime(str(res['h_ini'])[:5], "%H:%M").time()
                        r_fin = datetime.strptime(str(res['h_fin'])[:5], "%H:%M").time()
                        
                        if row["H_Ini"] < r_fin and r_ini < row["H_Fin"]:
                            tipo, icono = "reserva", "🟡"
                            detalle = f"RESERVA: {res['actividad']} ({res['nombre']})"
                            break
                except: continue

        st.markdown(f'<div class="bloque-item bloque-{tipo}"> <span class="time-text">{icono} {row["Hora"]}</span> {detalle}</div>', unsafe_allow_html=True)
