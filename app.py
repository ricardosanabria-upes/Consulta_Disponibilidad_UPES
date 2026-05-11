import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

# 1. Configuración de página limpia
st.set_page_config(page_title="UPES", layout="wide")

URL_SHEETS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
URL_GITHUB = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"

# 2. Funciones de Carga con Manejo de Errores Robusto
@st.cache_data(ttl=30)
def cargar_datos():
    # --- RESERVAS (SHEETS) ---
    try:
        r_raw = pd.read_csv(URL_SHEETS, skiprows=1)
        res = pd.DataFrame()
        # Forzamos la lectura por posición de columna para que no falle NUNCA
        res['user'] = r_raw.iloc[:, 3].astype(str)
        res['fecha'] = r_raw.iloc[:, 6].astype(str)
        res['aula'] = r_raw.iloc[:, 7].astype(str).str.strip()
        res['hi'] = r_raw.iloc[:, 8].astype(str)
        res['hf'] = r_raw.iloc[:, 9].astype(str)
        
        # Conversión segura de tiempos
        res['f_dt'] = pd.to_datetime(res['fecha'], dayfirst=True, errors='coerce').dt.date
        res['hi_dt'] = pd.to_datetime(res['hi'], errors='coerce').dt.time
        res['hf_dt'] = pd.to_datetime(res['hf'], errors='coerce').dt.time
        df_res = res.dropna(subset=['f_dt', 'hi_dt'])
    except Exception as e:
        st.error(f"Error en Sheets: {e}")
        df_res = pd.DataFrame()

    # --- HORARIO (GITHUB) ---
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
    except Exception as e:
        st.error(f"Error en GitHub: {e}")
        df_horario = None
        
    return df_res, df_horario

# 3. Lógica de Visualización
df_r, df_h = cargar_datos()

st.title("Sistema de Disponibilidad UPES")

if df_h is not None:
    # Selectores en columnas
    c1, c2 = st.columns(2)
    aula_sel = c1.selectbox("Seleccione Aula/Instalación", sorted(df_h["aula"].unique()))
    fecha_sel = c2.date_input("Fecha de consulta", value=date.today())

    # Mapeo de día de la semana
    d_n = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}
    dia_txt = d_n.get(fecha_sel.weekday())

    # Obtener bloques horarios únicos para el aula
    bloques = df_h[df_h["aula"] == aula_sel].drop_duplicates("hora_t").sort_values("hi")

    for _, b in bloques.iterrows():
        tipo_bloque = "LIBRE"
        detalle = "Disponible"
        color = "#f0fdf4" # Verde

        # A. Prioridad 1: Clases fijas
        m_c = df_h[(df_h["aula"] == aula_sel) & (df_h["dia"] == dia_txt) & (df_h["hora_t"] == b["hora_t"]) & (df_h["tipo"] == "clase")]
        
        if not m_c.empty:
            tipo_bloque = "CLASE"
            detalle = m_c.iloc[0]["info"]
            color = "#fef2f2" # Rojo
        else:
            # B. Prioridad 2: Reservas (Match por palabra clave para evitar fallos de nombre)
            if not df_r.empty:
                # Filtramos reservas del día y que contengan el nombre del aula
                palabra_aula = aula_sel.split()[0]
                m_r = df_r[(df_r["f_dt"] == fecha_sel) & (df_r["aula"].str.contains(palabra_aula, na=False))]
                
                for _, r in m_r.iterrows():
                    # Validación de cruce de horario
                    if (b["hi"] < r["hf_dt"]) and (r["hi_dt"] < b["hf"]):
                        tipo_bloque = "RESERVA"
                        detalle = f"RESERVADO: {r['user']}"
                        color = "#fff9db" # Amarillo
                        break

        # Renderizado de bloque sin HTML complejo para evitar SyntaxError
        st.info(f"**{b['hora_t']}** | {tipo_bloque} | {detalle}") if tipo_bloque != "LIBRE" else st.success(f"**{b['hora_t']}** | {tipo_bloque} | {detalle}")

# Panel de Depuración
with st.expander("Panel Técnico (Solo Admin)"):
    st.write("Datos de Reservas detectados:")
    st.dataframe(df_r)
