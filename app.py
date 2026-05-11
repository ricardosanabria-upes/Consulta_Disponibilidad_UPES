import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

# 1. Configuración básica
st.set_page_config(page_title="UPES", layout="wide")

URL_SHEETS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
URL_GITHUB = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"

@st.cache_data(ttl=5)
def cargar_datos():
    # RESERVAS: Lectura por posición para evitar errores de nombres
    try:
        r_raw = pd.read_csv(URL_SHEETS, skiprows=1, header=None, dtype=str)
        res = pd.DataFrame()
        res['u'] = r_raw.iloc[:, 3]
        res['f'] = r_raw.iloc[:, 6]
        res['a'] = r_raw.iloc[:, 7].str.strip().str.upper()
        res['hi'] = r_raw.iloc[:, 8]
        res['hf'] = r_raw.iloc[:, 9]
        res['f_dt'] = pd.to_datetime(res['f'], dayfirst=True, errors='coerce').dt.date
        res['hi_dt'] = pd.to_datetime(res['hi'], errors='coerce').dt.time
        res['hf_dt'] = pd.to_datetime(res['hf'], errors='coerce').dt.time
        df_res = res.dropna(subset=['f_dt', 'hi_dt'])
    except:
        df_res = pd.DataFrame()

    # HORARIO: GitHub
    try:
        resp = requests.get(URL_GITHUB)
        h_raw = pd.read_excel(io.BytesIO(resp.content))
        h_raw["Dia"] = h_raw["Dia"].ffill()
        h_raw["Hora"] = h_raw["Hora"].ffill()
        lista_h = []
        aulas = [c for c in h_raw.columns if c not in ["Dia", "Hora"]]
        for _, fila in h_raw.iterrows():
            try:
                t = str(fila["Hora"]).replace("–", "-")
                hi = datetime.strptime(t.split("-")[0].strip(), "%H:%M").time()
                hf = datetime.strptime(t.split("-")[1].strip(), "%H:%M").time()
                for a in aulas:
                    v = str(fila[a]).strip()
                    ocu = (v != "" and v.lower() != "nan")
                    lista_h.append({"d": str(fila["Dia"]), "h_t": t, "hi": hi, "hf": hf, "a": a.strip().upper(), "info": v if ocu else "L", "tipo": "C" if ocu else "L"})
            except: continue
        df_hor = pd.DataFrame(lista_h)
    except:
        df_hor = None
    return df_res, df_hor

df_r, df_h = cargar_datos()

st.title("Sistema de Disponibilidad UPES")

if df_h is not None:
    aula_sel = st.selectbox("Seleccione Instalación", sorted(df_h["a"].unique()))
    fecha_sel = st.date_input("Fecha", value=date.today())

    d_m = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}
    dia_txt = d_m.get(fecha_sel.weekday())

    bloques = df_h[df_h["a"] == aula_sel].drop_duplicates("h_t").sort_values("hi")

    for _, b in bloques.iterrows():
        # 1. ¿Hay Clase Fija?
        clase = df_h[(df_h["a"] == aula_sel) & (df_h["d"] == dia_txt) & (df_h["h_t"] == b["h_t"]) & (df_h["tipo"] == "C")]
        
        if not clase.empty:
            st.error(f"{b['h_t']} | CLASE: {clase.iloc[0]['info']}")
        else:
            # 2. ¿Hay Reserva? (Búsqueda flexible)
            res_ok = False
            if not df_r.empty:
                # Tomamos la primera palabra del aula para el cruce (ej: A-21)
                id_base = aula_sel.split()[0]
                m_r = df_r[(df_r["f_dt"] == fecha_sel) & (df_r["a"].str.contains(id_base, na=False))]
                
                for _, r in m_r.iterrows():
                    if (b["hi"] < r["hf_dt"]) and (r["hi_dt"] < b["hf"]):
                        st.warning(f"{b['h_t']} | RESERVA: {r['u']}")
                        res_ok = True
                        break
            
            if not res_ok:
                st.success(f"{b['h_t']} | Disponible")

st.write("---")
st.write("Total reservas cargadas:", len(df_r))
