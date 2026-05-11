import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

st.set_page_config(page_title="UPES", layout="wide")

URL_SHEETS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
URL_GITHUB = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"

@st.cache_data(ttl=30)
def cargar_datos():
    # 1. Cargar Reservas de Google Sheets
    try:
        r_sheets = pd.read_csv(URL_SHEETS, skiprows=1)
        res = pd.DataFrame()
        # Mapeo por posición exacta de columna para evitar errores de nombres
        res['user'] = r_sheets.iloc[:, 3].astype(str)
        res['fecha'] = r_sheets.iloc[:, 6].astype(str)
        res['aula'] = r_sheets.iloc[:, 7].astype(str).str.strip()
        res['hi'] = r_sheets.iloc[:, 8].astype(str)
        res['hf'] = r_sheets.iloc[:, 9].astype(str)
        
        # Normalización para match exacto
        res['aula'] = res['aula'].replace({
            "A-21": "A-21 C/Acondicionado",
            "A-22": "A-22 C/Acondicionado"
        })
        
        res['f_dt'] = pd.to_datetime(res['fecha'], dayfirst=True, errors='coerce').dt.date
        res['hi_dt'] = pd.to_datetime(res['hi'], errors='coerce').dt.time
        res['hf_dt'] = pd.to_datetime(res['hf'], errors='coerce').dt.time
        df_reservas = res.dropna(subset=['f_dt', 'hi_dt'])
    except:
        df_reservas = pd.DataFrame()

    # 2. Cargar Horario Base de GitHub
    try:
        resp = requests.get(URL_GITHUB)
        h_raw = pd.read_excel(io.BytesIO(resp.content))
        h_raw["Dia"] = h_raw["Dia"].ffill()
        h_raw["Hora"] = h_raw["Hora"].ffill()
        
        lista_h = []
        aulas = [c for c in h_raw.columns if c not in ["Dia", "Hora"]]
        for _, fila in h_raw.iterrows():
            try:
                h_txt = str(fila["Hora"]).replace("–", "-")
                h_partes = h_txt.split("-")
                hi = datetime.strptime(h_partes[0].strip(), "%H:%M").time()
                hf = datetime.strptime(h_partes[1].strip(), "%H:%M").time()
                for a in aulas:
                    val = str(fila[a]).strip()
                    ocupado = (val != "" and val.lower() != "nan")
                    lista_h.append({
                        "dia": str(fila["Dia"]), "hora_t": h_txt, "hi": hi, "hf": hf,
                        "aula": a.strip(), "info": val if ocupado else "Disponible", 
                        "tipo": "clase" if ocupado else "libre"
                    })
            except: continue
        df_horario = pd.DataFrame(lista_h)
    except:
        df_horario = None
        
    return df_reservas, df_horario

df_r, df_h = cargar_datos()

st.title("Sistema de Disponibilidad UPES")

if df_h is not None:
    # Selectores
    aula_sel = st.selectbox("Seleccione Instalación", sorted(df_h["aula"].unique()))
    fecha_sel = st.date_input("Fecha", value=date.today())

    # Mapeo de día
    dias = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}
    dia_txt = dias.get(fecha_sel.weekday())

    # Filtrar bloques del aula seleccionada
    bloques = df_h[df_h["aula"] == aula_sel].drop_duplicates("hora_t").sort_values("hi")

    for _, b in bloques.iterrows():
        # Por defecto: Disponible
        color, texto = "#f0fdf4", "Disponible"
        
        # 1. Prioridad: Clase fija (Match EXACTO de aula y hora)
        clase = df_h[(df_h["aula"] == aula_sel) & (df_h["dia"] == dia_txt) & (df_h["hora_t"] == b["hora_t"]) & (df_h["tipo"] == "clase")]
        
        if not clase.empty:
            color, texto = "#fef2f2", clase.iloc[0]["info"]
        else:
            # 2. Prioridad: Reserva (Match EXACTO de aula)
            if not df_r.empty:
                # FILTRO CRÍTICO: El nombre del aula debe ser idéntico
                m_r = df_r[(df_r["f_dt"] == fecha_sel) & (df_r["aula"] == aula_sel)]
                for _, r in m_r.iterrows():
                    # Verificar si la reserva cae en este bloque de tiempo
                    if (b["hi"] < r["hf_dt"]) and (r["hi_dt"] < b["hf"]):
                        color, texto = "#fff9db", f"RESERVA: {r['user']}"
                        break
        
        # Renderizar bloque
        st.markdown(f"""
        <div style="background:{color}; padding:12px; border-radius:8px; border:1px solid #ddd; margin-bottom:8px;">
            <b>{b['hora_t']}</b> | {texto}
        </div>
        """, unsafe_allow_html=True)

with st.expander("Panel de Control (Depuración)"):
    st.write(f"Reservas cargadas para {aula_sel}:", len(df_r[df_r['aula'] == aula_sel]))
    st.dataframe(df_r)
