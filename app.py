import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

st.set_page_config(page_title="UPES", layout="wide")

URL_S = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
URL_G = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"

@st.cache_data(ttl=5)
def load():
    # 1. RESERVAS: Limpieza profunda de nombres de aula
    try:
        r_raw = pd.read_csv(URL_S, skiprows=1, header=None, dtype=str)
        df_r = pd.DataFrame()
        df_r['u'] = r_raw.iloc[:, 3]
        df_r['f'] = pd.to_datetime(r_raw.iloc[:, 6], dayfirst=True, errors='coerce').dt.date
        # Guardamos solo la primera palabra del aula en mayúsculas (ej: "A-21")
        df_r['a'] = r_raw.iloc[:, 7].str.split().str[0].str.upper()
        df_r['hi'] = pd.to_datetime(r_raw.iloc[:, 8], errors='coerce').dt.time
        df_r['hf'] = pd.to_datetime(r_raw.iloc[:, 9], errors='coerce').dt.time
        df_r = df_r.dropna(subset=['f', 'hi'])
    except: df_r = pd.DataFrame()

    # 2. HORARIO BASE
    try:
        resp = requests.get(URL_G)
        h_raw = pd.read_excel(io.BytesIO(resp.content))
        h_raw["Dia"] = h_raw["Dia"].ffill()
        h_raw["Hora"] = h_raw["Hora"].ffill()
        list_h = []
        aus = [c for c in h_raw.columns if c not in ["Dia", "Hora"]]
        for _, f in h_raw.iterrows():
            try:
                t = str(f["Hora"]).replace("–", "-")
                hi = datetime.strptime(t.split("-")[0].strip(), "%H:%M").time()
                hf = datetime.strptime(t.split("-")[1].strip(), "%H:%M").time()
                for a in aus:
                    val = str(f[a]).strip()
                    occ = (val != "" and val.lower() != "nan")
                    list_h.append({"d": str(f["Dia"]), "h": t, "hi": hi, "hf": hf, "a": a.strip().upper(), "id": a.split()[0].upper(), "info": val if occ else "L", "tipo": "C" if occ else "L"})
            except: continue
        df_h = pd.DataFrame(list_h)
    except: df_h = None
    return df_r, df_h

res_data, hor_data = load()

st.title("Sistema de Disponibilidad UPES")

if hor_data is not None:
    # Selectores
    a_sel = st.selectbox("Seleccione Aula", sorted(hor_data["a"].unique()))
    f_sel = st.date_input("Fecha", value=date.today())
    
    d_m = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}
    d_txt = d_m.get(f_sel.weekday())

    # Filtrar bloques del aula
    blqs = hor_data[hor_data["a"] == a_sel].drop_duplicates("h").sort_values("hi")
    a_id = a_sel.split()[0] # ID base para comparar (ej: "A-21")

    for _, b in blqs.iterrows():
        # A. Verificar CLASE
        c = hor_data[(hor_data["a"] == a_sel) & (hor_data["d"] == d_txt) & (hor_data["h"] == b["h"]) & (hor_data["tipo"] == "C")]
        
        if not c.empty:
            st.error(f"{b['h']} | CLASE: {c.iloc[0]['info']}")
        else:
            # B. Verificar RESERVA (Comparación por ID de aula y Fecha)
            r_match = res_data[(res_data["f"] == f_sel) & (res_data["a"] == a_id)]
            
            find = False
            for _, r in r_match.iterrows():
                if (b["hi"] < r["hf"]) and (r["hi"] < b["hf"]):
                    st.warning(f"{b['h']} | RESERVA: {r['u']}")
                    find = True
                    break
            
            if not find:
                st.success(f"{b['h']} | Disponible")

st.divider()
st.write("Conexión: OK | Reservas en memoria:", len(res_data))
