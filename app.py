import streamlit as st
import pandas as pd
import io
from datetime import datetime, date

# 1. Configuración
st.set_page_config(page_title="UPES", layout="wide")

# CSS Simple para evitar errores de comillas largas
st.markdown("""
<style>
    .bloque { padding:10px; margin:5px; border-radius:8px; border:1px solid #ccc; }
    .libre { background-color: #f0fdf4; color: #166534; }
    .clase { background-color: #fef2f2; color: #991b1b; }
    .reserva { background-color: #fff9db; color: #856404; }
</style>
""", unsafe_allow_html=True)

URL_SHEETS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
URL_GITHUB = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"

# 2. Carga de Reservas (Google Sheets)
@st.cache_data(ttl=60)
def cargar_reservas():
    try:
        # Cargamos saltando la primera fila de título
        df = pd.read_csv(URL_SHEETS, skiprows=1)
        # Limpiar nombres de columnas de saltos de línea
        df.columns = [str(c).replace('\n', ' ').strip() for c in df.columns]
        
        # Encontrar columnas por palabra clave
        for c in df.columns:
            if "instalación" in c.lower() or "instalacion" in c.lower():
                df = df.rename(columns={c: "aula"})
            if "fecha" in c.lower():
                df = df.rename(columns={c: "fecha"})
            if "inicio" in c.lower():
                df = df.rename(columns={c: "h_ini"})
            if "finalización" in c.lower() or "finalizacion" in c.lower():
                df = df.rename(columns={c: "h_fin"})
            if "nombre" in c.lower() or "solicitante" in c.lower():
                df = df.rename(columns={c: "user"})

        # Normalizar nombres de aula
        if "aula" in df.columns:
            df["aula"] = df["aula"].astype(str).str.strip()
            df["aula"] = df["aula"].replace({"A-21": "A-21 C/Acondicionado", "A-22": "A-22 C/Acondicionado"})

        df["f_dt"] = pd.to_datetime(df["fecha"], dayfirst=True, errors='coerce').dt.date
        df["hi_dt"] = pd.to_datetime(df["h_ini"], errors='coerce').dt.time
        df["hf_dt"] = pd.to_datetime(df["h_fin"], errors='coerce').dt.time
        return df.dropna(subset=["aula", "f_dt", "hi_dt"])
    except:
        return pd.DataFrame()

# 3. Carga de Horario (GitHub)
@st.cache_data(ttl=3600)
def cargar_horario():
    try:
        import requests
        r = requests.get(URL_GITHUB)
        df_raw = pd.read_excel(io.BytesIO(r.content))
        df_raw["Dia"] = df_raw["Dia"].ffill()
        df_raw["Hora"] = df_raw["Hora"].ffill()
        
        filas = []
        aulas = [c for c in df_raw.columns if c not in ["Dia", "Hora"]]
        for _, row in df_raw.iterrows():
            try:
                h_txt = str(row["Hora"]).replace("–", "-")
                hi = datetime.strptime(h_txt.split("-")[0].strip(), "%H:%M").time()
                hf = datetime.strptime(h_txt.split("-")[1].strip(), "%H:%M").time()
                for a in aulas:
                    val = str(row[a]).strip()
                    ocupado = val != "" and val.lower() != "nan"
                    filas.append({
                        "dia": str(row["Dia"]), "hora_t": h_txt, "hi": hi, "hf": hf,
                        "aula": a.strip(), "desc": val if ocupado else "Disponible", 
                        "tipo": "clase" if ocupado else "libre"
                    })
            except: continue
        return pd.DataFrame(filas)
    except: return None

# 4. Interfaz
st.title("🏫 Control UPES")

df_h = cargar_horario()
df_r = cargar_reservas()

# Selectores
aulas_lista = sorted(df_h["aula"].unique()) if df_h is not None else ["A-11"]
col1, col2 = st.columns(2)
aula_sel = col1.selectbox("Aula", aulas_lista)
fecha_sel = col2.date_input("Fecha", value=date.today())

# Mapeo de día
dias_esp = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}
nombre_dia = dias_esp.get(fecha_sel.weekday())

if df_h is not None:
    bloques = df_h[df_h["aula"] == aula_sel].drop_duplicates("hora_t").sort_values("hi")
    
    for _, b in bloques.iterrows():
        tipo, det = "libre", "Disponible"
        
        # Clase
        c_match = df_h[(df_h["aula"] == aula_sel) & (df_h["dia"] == nombre_dia) & (df_h["hora_t"] == b["hora_t"]) & (df_h["tipo"] == "clase")]
        if not c_match.empty:
            tipo, det = "clase", c_match.iloc[0]["desc"]
        else:
            # Reserva
            if not df_r.empty:
                r_match = df_r[(df_r["aula"] == aula_sel) & (df_r["f_dt"] == fecha_sel)]
                for _, r in r_match.iterrows():
                    if (b["hi"] < r["hf_dt"]) and (r["hi_dt"] < b["hf"]):
                        tipo, det = "reserva", f"RESERVA: {r['user']}"
                        break
        
        # Dibujar bloque
        clase_css = f"bloque {tipo}"
        st.markdown(f"<div class='{clase_css}'><b>{b['hora_t']}</b> - {det}</div>", unsafe_allow_html=True)

with st.expander("Ver Datos de Google Sheets"):
    st.write(df_r)
