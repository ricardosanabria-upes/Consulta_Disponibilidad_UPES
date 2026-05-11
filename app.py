import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

st.set_page_config(page_title="UPES", layout="wide")

# URLs de conexión
U_SHEETS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
U_GIT = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"

@st.cache_data(ttl=10)
def cargar_datos():
    # 1. RESERVAS (Lectura ultra-segura por posición)
    try:
        r_raw = pd.read_csv(U_SHEETS, skiprows=1, header=None, dtype=str)
        res = pd.DataFrame()
        res['usuario'] = r_raw.iloc[:, 3]
        res['fecha'] = r_raw.iloc[:, 6]
        res['aula'] = r_raw.iloc[:, 7].str.strip()
        res['hi'] = r_raw.iloc[:, 8]
        res['hf'] = r_raw.iloc[:, 9]
        
        res['f_dt'] = pd.to_datetime(res['fecha'], dayfirst=True, errors='coerce').dt.date
        res['hi_dt'] = pd.to_datetime(res['hi'], errors='coerce').dt.time
        res['hf_dt'] = pd.to_datetime(res['hf'], errors='coerce').dt.time
        df_res = res.dropna(subset=['f_dt', 'hi_dt'])
    except:
        df_res = pd.DataFrame()

    # 2. HORARIO BASE
    try:
        resp = requests.get(U_GIT)
        h_raw = pd.read_excel(io.BytesIO(resp.content))
        h_raw["Dia"] = h_raw["Dia"].ffill()
        h_raw["Hora"] = h_raw["Hora"].ffill()
        lista = []
        aulas = [c for c in h_raw.columns if c not in ["Dia", "Hora"]]
        for _, fila in h_raw.iterrows():
            try:
                t = str(fila["Hora"]).replace("–", "-")
                hi = datetime.strptime(t.split("-")[0].strip(), "%H:%M").time()
                hf = datetime.strptime(t.split("-")[1].strip(), "%H:%M").time()
                for a in aulas:
                    v = str(fila[a]).strip()
                    ocu = (v != "" and v.lower() != "nan")
                    lista.append({"d": str(fila["Dia"]), "h": t, "hi": hi, "hf": hf, "a": a.strip(), "i": v if ocu else "D", "t": "C" if ocu else "L"})
            except: continue
        df_hor = pd.DataFrame(lista)
    except:
        df_hor = None
    return df_res, df_hor

df_r, df_h = cargar_datos()

st.title("Control UPES")

if df_h is not None:
    # Selectores
    aula_sel = st.selectbox("Instalación", sorted(df_h["a"].unique()))
    fecha_sel = st.date_input("Fecha", value=date.today())

    d_map = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}
    dia_txt = d_map.get(fecha_sel.weekday())

    # Bloques del aula
    bloques = df_h[df_h["a"] == aula_sel].drop_duplicates("h").sort_values("hi")

    for _, b in bloques.iterrows():
        # A. Revisar Clase Fija
        clase = df_h[(df_h["a"] == aula_sel) & (df_h["d"] == dia_txt) & (df_h["h"] == b["h"]) & (df_h["t"] == "C")]
        
        if not clase.empty:
            st.error(f"{b['h']} | CLASE: {clase.iloc[0]['i']}")
        else:
            # B. Revisar Reserva en Google Sheets
            reservado = False
            if not df_r.empty:
                # Comparamos solo la primera palabra para evitar errores de formato (A-21, A-22, etc)
                base_aula = aula_sel.split()[0]
                m_r = df_r[(df_r["f_dt"] == fecha_sel) & (df_r["aula"].str.contains(base_aula, na=False))]
                
                for _, r in m_r.iterrows():
                    if (b["hi"] < r["hf_dt"]) and (r["hi_dt"] < b["hf"]):
                        st.warning(f"{b['h']} | RESERVADO: {r['usuario']}")
                        reservado = True
                        break
            
            if not reservado:
                st.success(f"{b['h']} | Disponible")

# Verificación de carga (ayuda a saber si Sheets está conectado)
st.write(f"Conexión con Reservas: {'ACTIVA' if not df_r.empty else 'SIN DATOS'}")
