import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

# ─── CONFIGURACIÓN ───────────────────────────────────────────────────────────
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
        df_res = pd.DataFrame({
            'act': tmp.iloc[:, 4],
            'fec': pd.to_datetime(tmp.iloc[:, 6], dayfirst=True, errors='coerce').dt.date,
            'aula': tmp.iloc[:, 7].astype(str).str.strip(),
            'ini': tmp.iloc[:, 8].astype(str).str.strip(),
            'fin': tmp.iloc[:, 9].astype(str).str.strip(),
            'user': tmp.iloc[:, 3]
        })
    except: pass

    # 2. HORARIO (GITHUB)
    url_hor = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"
    df_hor = pd.DataFrame()
    aulas = []
    try:
        resp = requests.get(url_hor)
        xl = pd.read_excel(io.BytesIO(resp.content))
        # Rellenar días y horas hacia abajo
        xl["Dia"] = xl["Dia"].ffill()
        xl["Hora"] = xl["Hora"].ffill()
        # Aulas son todas las columnas excepto Dia y Hora
        aulas = [c for c in xl.columns if str(c).strip() not in ["Dia", "Hora", "DIA", "HORA"]]
        df_hor = xl
    except: pass
    
    return df_res, df_hor, aulas

df_r, df_h, lista_aulas = cargar_datos()

# ─── INTERFAZ ────────────────────────────────────────────────────────────────
st.title("🏫 Control de Aulas UPES")

if not lista_aulas:
    st.error("No se pudo cargar el horario de GitHub.")
else:
    c1, c2 = st.columns(2)
    aula_sel = c1.selectbox("Seleccione Aula", lista_aulas)
    fecha_sel = c2.date_input("Fecha", value=date.today())

    # Mapeo de día (debe coincidir con el Excel)
    dias_nombres = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    dia_str = dias_nombres[fecha_sel.weekday()]

    st.subheader(f"Disponibilidad: {aula_sel} — {fecha_sel.strftime('%d/%m/%Y')}")

    # Filtrar el Excel por el día seleccionado (buscamos la palabra del día en la columna Dia)
    # Usamos .str.contains por si en el excel dice "1.Lunes"
    horario_dia = df_h[df_h["Dia"].astype(str).str.contains(dia_str, case=False, na=False)]

    if horario_dia.empty:
        st.warning(f"No hay clases programadas para el día {dia_str}.")
    else:
        for _, row in horario_dia.iterrows():
            hora_bloque = str(row["Hora"]).replace("–", "-").strip()
            valor_celda = row[aula_sel]
            
            # Estado inicial según el Excel
            esta_ocupado = not (pd.isna(valor_celda) or str(valor_celda).strip() == "")
            tipo = "clase" if esta_ocupado else "libre"
            icono = "🔴" if esta_ocupado else "✅"
            detalle = str(valor_celda) if esta_ocupado else "Libre"

            # Cruce con Reservas de Google (SOLO si el aula coincide exactamente)
            if not esta_ocupado:
                res_hoy = df_r[(df_r['fec'] == fecha_sel) & (df_r['aula'] == str(aula_sel).strip())]
                
                for _, res in res_hoy.iterrows():
                    try:
                        # Extraer solo HH:MM
                        h_ini_res = ":".join(res['ini'].split(":")[:2])
                        # Si la hora de inicio de la reserva está dentro de este bloque de texto
                        if h_ini_res in hora_bloque:
                            tipo, icono, detalle = "reserva", "🟡", f"RESERVA: {res['act']} ({res['user']})"
                            break
                    except: continue

            st.markdown(f'<div class="bloque {tipo}"><span class="time-badge">{icono} {hora_bloque}</span> {detalle}</div>', unsafe_allow_html=True)
