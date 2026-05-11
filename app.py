import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

st.set_page_config(page_title="UPES", layout="wide")

# URLs
URL_SHEETS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
URL_GITHUB = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"

@st.cache_data(ttl=5)
def cargar_datos():
    # 1. RESERVAS (Google Sheets) - Lectura por posición para evitar nombres largos
    try:
        r_raw = pd.read_csv(URL_SHEETS, skiprows=1, header=None, dtype=str)
        res = pd.DataFrame()
        res['usuario'] = r_raw.iloc[:, 3]
        res['fecha'] = r_raw.iloc[:, 6]
        res['aula_res'] = r_raw.iloc[:, 7].str.strip().str.upper() # Todo a MAYÚSCULAS
        res['hi'] = r_raw.iloc[:, 8]
        res['hf'] = r_raw.iloc[:, 9]
        
        res['f_dt'] = pd.to_datetime(res['fecha'], dayfirst=True, errors='coerce').dt.date
        res['hi_dt'] = pd.to_datetime(res['hi'], errors='coerce').dt.time
        res['hf_dt'] = pd.to_datetime(res['hf'], errors='coerce').dt.time
        df_res = res.dropna(subset=['f_dt', 'hi_dt'])
    except:
        df_res = pd.DataFrame()

    # 2. HORARIO (GitHub)
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
                h_ini = datetime.strptime(h_txt.split("-")[0].strip(), "%H:%M").time()
                h_fin = datetime.strptime(h_txt.split("-")[1].strip(), "%H:%M").time()
                for a in aulas_cols:
                    v = str(fila[a]).strip()
                    ocu = (v != "" and v.lower() != "nan")
                    lista_h.append({
                        "dia": str(fila["Dia"]), "hora_t": h_txt, "hi": h_ini, "hf": h_fin,
                        "aula_nom": a.strip(), "info": v if ocu else "Libre", "tipo": "C" if ocu else "L"
                    })
            except: continue
        df_hor = pd.DataFrame(lista_h)
    except:
        df_hor = None
    return df_res, df_hor

df_r, df_h = cargar_datos()

st.title("Sistema de Disponibilidad UPES")

if df_h is not None:
    # Selectores
    aula_sel = st.selectbox("Seleccione Aula", sorted(df_h["aula_nom"].unique()))
    fecha_sel = st.date_input("Fecha de consulta", value=date.today())

    # Mapeo de día
    d_m = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}
    dia_txt = d_m.get(fecha_sel.weekday())

    # Bloques del aula
    bloques = df_h[df_h["aula_nom"] == aula_sel].drop_duplicates("hora_t").sort_values("hi")

    for _, b in bloques.iterrows():
        # Filtro de Clase Fija
        clase = df_h[(df_h["aula_nom"] == aula_sel) & (df_h["dia"] == dia_txt) & (df_h["hora_t"] == b["hora_t"]) & (df_h["tipo"] == "C")]
        
        if not clase.empty:
            st.error(f"{b['hora_t']} | CLASE: {clase.iloc[0]['info']}")
        else:
            # Filtro de Reserva (Match más flexible para evitar que salga "Disponible")
            res_found = False
            if not df_r.empty:
                # Sacamos la identificación base (ej: "A-21")
                id_base = aula_sel.split()[0].upper()
                m_res = df_r[(df_r["f_dt"] == fecha_sel) & (df_r["aula_res"].str.contains(id_base, na=False))]
                
                for _, r in m_res.iterrows():
                    if (b["hi"] < r["hf_dt"]) and (r["hi_dt"] < b["hf"]):
                        st.warning(f"{b['hora_t']} | RESERVADO: {r['usuario']}")
                        res_found = True
                        break
            
            if not res_found:
                st.success(f"{b['hora_t']} | Disponible")

st.info("Nota: Si las reservas no aparecen, verifica que el enlace de Google Sheets esté publicado como CSV.")
