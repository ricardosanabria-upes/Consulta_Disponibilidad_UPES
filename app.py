import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

# ─── CONFIGURACIÓN E INTERFAZ ────────────────────────────────────────────────
st.set_page_config(page_title="UPES - Disponibilidad de Aulas", layout="wide")

st.markdown("""
<style>
    .bloque { padding: 15px; border-radius: 10px; margin-bottom: 8px; border: 1px solid #ddd; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; transition: 0.3s; }
    .clase { background-color: #ffebee; color: #b71c1c; border-left: 6px solid #b71c1c; }
    .libre { background-color: #e8f5e9; color: #1b5e20; border-left: 6px solid #1b5e20; }
    .reserva { background-color: #fff9c4; color: #827717; border-left: 6px solid #fbc02d; font-weight: bold; box-shadow: 0px 2px 5px rgba(0,0,0,0.1); }
    .time-badge { font-size: 1.1rem; margin-right: 15px; }
</style>
""", unsafe_allow_html=True)

def limpiar_id(t):
    if pd.isna(t): return ""
    return "".join(filter(str.isalnum, str(t))).upper()

# ─── CARGA DE DATOS ──────────────────────────────────────────────────────────
@st.cache_data(ttl=15)
def cargar_datos():
    # 1. RESERVAS (GOOGLE SHEETS)
    url_res = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
    try:
        res_raw = requests.get(url_res).text.splitlines()
        start_row = 0
        for i, line in enumerate(res_raw):
            if "Marca temporal" in line:
                start_row = i
                break
        df_res = pd.read_csv(io.StringIO("\n".join(res_raw[start_row:])))
        
        reservas = pd.DataFrame()
        reservas['actividad'] = df_res.iloc[:, 4]
        # Forzamos día primero para evitar el error de Mayo/Febrero
        reservas['fecha'] = pd.to_datetime(df_res.iloc[:, 6], dayfirst=True, errors='coerce').dt.date
        reservas['aula_id'] = df_res.iloc[:, 7].apply(limpiar_id)
        reservas['h_ini'] = df_res.iloc[:, 8].astype(str)
        reservas['h_fin'] = df_res.iloc[:, 9].astype(str)
        reservas['nombre'] = df_res.iloc[:, 3]
    except:
        reservas = pd.DataFrame()

    # 2. HORARIO (GITHUB)
    url_hor = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"
    try:
        resp = requests.get(url_hor)
        df_hor = pd.read_excel(io.BytesIO(resp.content))
        df_hor["Dia"] = df_hor["Dia"].ffill()
        df_hor["Hora"] = df_hor["Hora"].ffill()
        
        horario_lista = []
        columnas_aulas = [c for c in df_hor.columns if c not in ["Dia", "Hora"]]
        for _, row in df_hor.iterrows():
            try:
                h_range = str(row["Hora"]).replace("–", "-").split("-")
                h_ini = datetime.strptime(h_range[0].strip(), "%H:%M").time()
                h_fin = datetime.strptime(h_range[1].strip(), "%H:%M").time()
                for aula in columnas_aulas:
                    val = row[aula]
                    ocupado = not (pd.isna(val) or str(val).strip() == "")
                    horario_lista.append({
                        "Dia": str(row["Dia"]).strip(),
                        "HoraStr": str(row["Hora"]),
                        "H_Ini": h_ini, "H_Fin": h_fin,
                        "AulaID": limpiar_id(aula),
                        "Detalle": str(val).strip() if ocupado else "Libre",
                        "Ocupado": ocupado
                    })
            except: continue
        horario = pd.DataFrame(horario_lista)
    except:
        horario = pd.DataFrame()

    return reservas, horario

df_r, df_h = cargar_datos()

# ─── VISTA DE LA APP ─────────────────────────────────────────────────────────
st.title("🏫 Control de Aulas UPES")

col1, col2 = st.columns(2)
with col1:
    aula_sel = st.selectbox("Seleccione la Instalación", ["A-11", "A-12", "A-13", "A-14", "A-15", "A-16", "A-21 C/Acondicionado", "A-22 C/Acondicionado", "A-31", "A-32", "A-33", "A-34 (Mesas de dibujo)", "SUM", "BIBLIOTECA"])
with col2:
    fecha_sel = st.date_input("Fecha de consulta", value=date.today())

dias_map = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}
dia_nombre = dias_map[fecha_sel.weekday()]

if not df_h.empty:
    id_buscado = limpiar_id(aula_sel)
    bloques = df_h[(df_h["AulaID"] == id_buscado) & (df_h["Dia"] == dia_nombre)]
    
    st.subheader(f"Disponibilidad: {aula_sel} — {fecha_sel.strftime('%d/%m/%Y')}")
    
    if bloques.empty:
        st.warning("No se encontraron registros para este día en el horario base.")
    else:
        for _, row in bloques.iterrows():
            tipo = "clase" if row["Ocupado"] else "libre"
            detalle = row["Detalle"]
            icono = "🔴" if row["Ocupado"] else "✅"
            
            # CRUCE CON RESERVAS (Solo si el bloque está libre en el horario base)
            if not row["Ocupado"] and not df_r.empty:
                match = df_r[(df_r['fecha'] == fecha_sel) & (df_r['aula_id'] == id_buscado)]
                
                for _, res in match.iterrows():
                    try:
                        # Extraer solo HH:MM del formato "HH:MM:SS"
                        r_ini_parts = res['h_ini'].strip().split(":")
                        r_fin_parts = res['h_fin'].strip().split(":")
                        
                        res_ini = datetime.strptime(f"{r_ini_parts[0]}:{r_ini_parts[1]}", "%H:%M").time()
                        res_fin = datetime.strptime(f"{r_fin_parts[0]}:{r_fin_parts[1]}", "%H:%M").time()
                        
                        # Comprobar traslape de tiempos
                        if row["H_Ini"] < res_fin and res_ini < row["H_Fin"]:
                            tipo = "reserva"
                            detalle = f"RESERVA: {res['actividad']} ({res['nombre']})"
                            icono = "🟡"
                            break
                    except: continue

            st.markdown(f"""
                <div class="bloque {tipo}">
                    <span class="time-badge">{icono} {row['HoraStr']}</span>
                    <span>{detalle}</span>
                </div>
            """, unsafe_allow_html=True)
