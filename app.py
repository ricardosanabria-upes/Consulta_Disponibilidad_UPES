import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

# 1. Configuración de página - Cero HTML para evitar SyntaxError
st.set_page_config(page_title="UPES", layout="wide")

URL_SHEETS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
URL_GITHUB = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"

@st.cache_data(ttl=10)
def cargar_datos():
    # --- RESERVAS (SHEETS) ---
    try:
        r_raw = pd.read_csv(URL_SHEETS, skiprows=1, dtype=str)
        res = pd.DataFrame()
        # Selección por posición: 3=User, 6=Fecha, 7=Aula, 8=Inicio, 9=Fin
        res['u'] = r_raw.iloc[:, 3]
        res['f'] = r_raw.iloc[:, 6]
        res['a'] = r_raw.iloc[:, 7].str.strip()
        res['hi'] = r_raw.iloc[:, 8]
        res['hf'] = r_raw.iloc[:, 9]
        # Conversión de tiempos
        res['f_dt'] = pd.to_datetime(res['f'], dayfirst=True, errors='coerce').dt.date
        res['hi_dt'] = pd.to_datetime(res['hi'], errors='coerce').dt.time
        res['hf_dt'] = pd.to_datetime(res['hf'], errors='coerce').dt.time
        df_res = res.dropna(subset=['f_dt', 'hi_dt'])
    except:
        df_res = pd.DataFrame()

    # --- HORARIO (GITHUB) ---
    try:
        resp = requests.get(URL_GITHUB)
        h_raw = pd.read_excel(io.BytesIO(resp.content))
        h_raw["Dia"] = h_raw["Dia"].ffill()
        h_raw["Hora"] = h_raw["Hora"].ffill()
        lista_h = []
        aulas_cols = [c for c in h_raw.columns if c not in ["Dia", "Hora"]]
        for _, fila in h_raw.iterrows():
            try:
                h_txt = str(fila["Hora"]).replace("–", "-")
                hi = datetime.strptime(h_txt.split("-")[0].strip(), "%H:%M").time()
                hf = datetime.strptime(h_txt.split("-")[1].strip(), "%H:%M").time()
                for a in aulas_cols:
                    v = str(fila[a]).strip()
                    ocu = (v != "" and v.lower() != "nan")
                    lista_h.append({
                        "dia": str(fila["Dia"]), "hora_t": h_txt, "hi": hi, "hf": hf,
                        "aula": a.strip(), "info": v if ocu else "Disponible", "tipo": "C" if ocu else "L"
                    })
            except: continue
        df_hor = pd.DataFrame(lista_h)
    except:
        df_hor = None
    return df_res, df_hor

df_r, df_h = cargar_datos()

st.title("Disponibilidad UPES")

if df_h is not None:
    aula_sel = st.selectbox("Instalación", sorted(df_h["aula"].unique()))
    fecha_sel = st.date_input("Fecha", value=date.today())
    d_m = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}
    dia_n = d_m.get(fecha_sel.weekday())

    bloques = df_h[df_h["aula"] == aula_sel].drop_duplicates("hora_t").sort_values("hi")

    for _, b in bloques.iterrows():
        clase = df_h[(df_h["aula"] == aula_sel) & (df_h["dia"] == dia_n) & (df_h["hora_t"] == b["hora_t"]) & (df_h["tipo"] == "C")]
        
        if not clase.empty:
            st.error(f"**{b['hora_t']}** | CLASE: {clase.iloc[0]['info']}")
        else:
            reservado = False
            if not df_r.empty:
                # Comparamos solo la primera palabra (ej: "A-21") para que el match sea seguro
                id_aula = aula_sel.split()[0]
                m_res = df_r[(df_r["f_dt"] == fecha_sel) & (df_r["a"].str.contains(id_aula, na=False))]
                for _, r in m_res.iterrows():
                    if (b["hi"] < r["hf_dt"]) and (r["hi_dt"] < b["hf"]):
                        st.warning(f"**{b['hora_t']}** | RESERVADO: {r['u']}")
                        reservado = True
                        break
            if not reservado:
                st.success(f"**{b['hora_t']}** | Disponible")

with st.expander("Verificar Datos"):
    st.write(df_r)
