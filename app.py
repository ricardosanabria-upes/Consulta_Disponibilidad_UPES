import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

st.set_page_config(page_title="UPES", layout="wide")

# URLs de datos
U_SHEETS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
U_GIT = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"

@st.cache_data(ttl=15)
def cargar_todo():
    # 1. RESERVAS
    try:
        r_raw = pd.read_csv(U_SHEETS, skiprows=1, header=None, dtype=str)
        res = pd.DataFrame()
        res['u'] = r_raw.iloc[:, 3]
        res['f'] = r_raw.iloc[:, 6]
        res['a'] = r_raw.iloc[:, 7].str.strip()
        res['hi'] = r_raw.iloc[:, 8]
        res['hf'] = r_raw.iloc[:, 9]
        res['f_dt'] = pd.to_datetime(res['f'], dayfirst=True, errors='coerce').dt.date
        res['hi_dt'] = pd.to_datetime(res['hi'], errors='coerce').dt.time
        res['hf_dt'] = pd.to_datetime(res['hf'], errors='coerce').dt.time
        d_res = res.dropna(subset=['f_dt', 'hi_dt'])
    except:
        d_res = pd.DataFrame()

    # 2. HORARIO
    try:
        resp = requests.get(U_GIT)
        h_raw = pd.read_excel(io.BytesIO(resp.content))
        h_raw["Dia"] = h_raw["Dia"].ffill()
        h_raw["Hora"] = h_raw["Hora"].ffill()
        lista = []
        cols = [c for c in h_raw.columns if c not in ["Dia", "Hora"]]
        for _, fila in h_raw.iterrows():
            try:
                txt = str(fila["Hora"]).replace("–", "-")
                hi = datetime.strptime(txt.split("-")[0].strip(), "%H:%M").time()
                hf = datetime.strptime(txt.split("-")[1].strip(), "%H:%M").time()
                for a in cols:
                    v = str(fila[a]).strip()
                    ocu = (v != "" and v.lower() != "nan")
                    lista.append({"d": str(fila["Dia"]), "h_t": txt, "hi": hi, "hf": hf, "a": a.strip(), "i": v if ocu else "Disponible", "t": "C" if ocu else "L"})
            except: continue
        d_hor = pd.DataFrame(lista)
    except:
        d_hor = None
    return d_res, d_hor

df_r, df_h = cargar_todo()

st.title("Disponibilidad UPES")

if df_h is not None:
    # Selectores
    a_sel = st.selectbox("Instalación", sorted(df_h["a"].unique()))
    f_sel = st.date_input("Fecha", value=date.today())

    d_map = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}
    dia_txt = d_map.get(f_sel.weekday())

    # Bloques
    bloques = df_h[df_h["a"] == a_sel].drop_duplicates("h_t").sort_values("hi")

    for _, b in bloques.iterrows():
        # Clase fija
        c = df_h[(df_h["a"] == a_sel) & (df_h["d"] == dia_txt) & (df_h["h_t"] == b["h_t"]) & (df_h["t"] == "C")]
        
        if not c.empty:
            st.error(f"{b['h_t']} | CLASE: {c.iloc[0]['i']}")
        else:
            # Reserva
            r_encontrada = False
            if not df_r.empty:
                # Match simplificado por primera palabra
                m_r = df_r[(df_r["f_dt"] == f_sel) & (df_r["a"].str.contains(a_sel.split()[0], na=False))]
                for _, r in m_r.iterrows():
                    if (b["hi"] < r["hf_dt"]) and (r["hi_dt"] < b["hf"]):
                        st.warning(f"{b['h_t']} | RESERVADO: {r['u']}")
                        r_encontrada = True
                        break
            
            if not r_encontrada:
                st.success(f"{b['h_t']} | Disponible")

st.divider()
st.write("Reservas en sistema:", len(df_r))
