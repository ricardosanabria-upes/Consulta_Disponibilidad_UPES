import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

# ─── CONFIGURACIÓN VISUAL ─────────────────────────────────────────────────────
st.set_page_config(page_title="UPES - Control de Aulas", layout="wide")

st.markdown("""
<style>
    .bloque { padding: 15px; border-radius: 10px; margin-bottom: 8px; border: 1px solid #ddd; font-family: sans-serif; }
    .clase { background-color: #ffebee; color: #b71c1c; border-left: 6px solid #b71c1c; }
    .libre { background-color: #e8f5e9; color: #1b5e20; border-left: 6px solid #1b5e20; }
    .reserva { background-color: #fff9c4; color: #827717; border-left: 6px solid #fbc02d; font-weight: bold; }
    .time-badge { font-weight: bold; margin-right: 15px; font-size: 1.1em; }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=5)
def cargar_datos():
    # 1. RESERVAS (GOOGLE SHEETS)
    url_res = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
    df_res = pd.DataFrame()
    try:
        r = requests.get(url_res).text.splitlines()
        idx = next(i for i, line in enumerate(r) if "Marca temporal" in line)
        tmp = pd.read_csv(io.StringIO("\n".join(r[idx:])))
        
        # PROCESAMIENTO CRÍTICO DE FECHA: Forzamos día primero para evitar el error de mes/día
        df_res = pd.DataFrame({
            'act': tmp.iloc[:, 4],
            'fec': pd.to_datetime(tmp.iloc[:, 6], dayfirst=True, errors='coerce').dt.date,
            'aula': tmp.iloc[:, 7].astype(str).str.strip(),
            'ini': tmp.iloc[:, 8].astype(str).str.strip(),
            'fin': tmp.iloc[:, 9].astype(str).str.strip(),
            'user': tmp.iloc[:, 3]
        })
    except: pass

    # 2. HORARIO BASE (GITHUB)
    url_hor = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"
    df_hor = pd.DataFrame()
    aulas = []
    try:
        resp = requests.get(url_hor)
        xl = pd.read_excel(io.BytesIO(resp.content))
        xl["Dia"] = xl["Dia"].ffill()
        xl["Hora"] = xl["Hora"].ffill()
        # Filtramos columnas para que NO aparezcan "Dia" o "Hora" en la lista de selección
        aulas = [c for c in xl.columns if str(c).strip() not in ["Dia", "Hora", "DIA", "HORA"]]
        df_hor = xl
    except: pass
    
    return df_res, df_hor, aulas

df_r, df_h, lista_aulas = cargar_datos()

# ─── INTERFAZ ────────────────────────────────────────────────────────────────
st.title("🏫 Control de Aulas UPES")

if not lista_aulas:
    st.error("No se pudo cargar el archivo de Excel. Revisa el enlace de GitHub.")
else:
    c1, c2 = st.columns(2)
    # Seleccionamos aula del menú limpio
    aula_sel = c1.selectbox("Seleccione la Instalación", lista_aulas)
    fecha_sel = c2.date_input("Fecha de consulta", value=date.today())

    # Mapeo de días flexible
    nombres_dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    dia_buscado = nombres_dias[fecha_sel.weekday()]

    st.subheader(f"Disponibilidad: {aula_sel} — {fecha_sel.strftime('%d/%m/%Y')}")

    # Filtrar el horario base por el día seleccionado
    bloques_dia = df_h[df_h["Dia"].astype(str).str.contains(dia_buscado, case=False, na=False)]

    if bloques_dia.empty:
        st.warning(f"No hay bloques definidos para el día {dia_buscado}.")
    else:
        for _, row in bloques_dia.iterrows():
            hora_str = str(row["Hora"]).replace("–", "-").strip()
            detalle_excel = row[aula_sel]
            
            # 1. Determinar estado inicial (Excel)
            ocupado_excel = not (pd.isna(detalle_excel) or str(detalle_excel).strip() == "")
            tipo = "clase" if ocupado_excel else "libre"
            icono = "🔴" if ocupado_excel else "✅"
            texto = str(detalle_excel) if ocupado_excel else "Libre"

            # 2. Cruce con Reservas de Google (Solo si el bloque está 'Libre' en el Excel)
            if not ocupado_excel:
                # Filtro estricto: Fecha exacta y Aula exacta
                reservas_match = df_r[(df_r['fec'] == fecha_sel) & (df_r['aula'] == str(aula_sel).strip())]
                
                for _, res in reservas_match.iterrows():
                    try:
                        # Extraemos la hora de inicio de la reserva (ej. '9:00:00' -> '9:00')
                        h_ini_res = ":".join(res['ini'].split(":")[:2])
                        # Si la hora de inicio de la reserva está contenida en el texto del bloque (ej. '08:00-09:40')
                        if h_ini_res in hora_str or h_ini_res.replace("0", "", 1) in hora_str:
                            tipo, icono, texto = "reserva", "🟡", f"RESERVA: {res['act']} ({res['user']})"
                            break
                    except: continue

            st.markdown(f'<div class="bloque {tipo}"><span class="time-badge">{icono} {hora_str}</span> {texto}</div>', unsafe_allow_html=True)
