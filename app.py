import streamlit as st
import pandas as pd
import io
from datetime import datetime, date

# 1. Configuración básica
st.set_page_config(page_title="UPES", layout="wide")

# CSS simplificado en una sola línea para evitar errores de sintaxis
st.markdown("<style>.b {padding:10px;margin:5px;border-radius:8px;border:1px solid #ccc;} .libre{background:#f0fdf4;} .clase{background:#fef2f2;} .reserva{background:#fff9db;}</style>", unsafe_allow_html=True)

URL_SHEETS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
URL_GITHUB = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"

# 2. Carga de Reservas
@st.cache_data(ttl=60)
def cargar_reservas():
    try:
        # Cargamos saltando la fila de título
        df = pd.read_csv(URL_SHEETS, skiprows=1)
        # Limpiar nombres de columnas (solo quitar espacios laterales)
        df.columns = [str(c).strip() for c in df.columns]
        
        # Mapeo manual por posición para evitar errores con nombres largos
        # Columna D(3): Nombre, G(6): Fecha, H(7): Aula, I(8): Inicio, J(9): Fin
        columnas = df.columns.tolist()
        df = df.rename(columns={
            columnas[3]: "user",
            columnas[6]: "fecha",
            columnas[7]: "aula",
            columnas[8]: "h_ini",
            columnas[9]: "h_fin"
        })

        # Convertir a texto y limpiar individualmente para evitar el error '.str'
        df["aula"] = df["aula"].apply(lambda x: str(x).strip())
        df["aula"] = df["aula"].replace({"A-21": "A-21 C/Acondicionado", "A-22": "A-22 C/Acondicionado"})
        
        df["f_dt"] = pd.to_datetime(df["fecha"], dayfirst=True, errors='coerce').dt.date
        df["hi_dt"] = pd.to_datetime(df["h_ini"], errors='coerce').dt.time
        df["hf_dt"] = pd.to_datetime(df["h_fin"], errors='coerce').dt.time
        
        return df.dropna(subset=["aula", "f_dt", "hi_dt"])
    except:
        return pd.DataFrame()

# 3. Carga de Horario
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
                h_partes = h_txt.split("-")
                hi = datetime.strptime(h_partes[0].strip(), "%H:%M").time()
                hf = datetime.strptime(h_partes[1].strip(), "%H:%M").time()
                for a in aulas:
                    val = str(row[a]).strip()
                    es_clase = (val != "" and val.lower() != "nan")
                    filas.append({
                        "dia": str(row["Dia"]), "hora_t": h_txt, "hi": hi, "hf": hf,
                        "aula": a.strip(), "desc": val if es_clase else "Disponible", 
                        "tipo": "clase" if es_clase else "libre"
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
c1, c2 = st.columns(2)
aula_sel = c1.selectbox("Aula", aulas_lista)
fecha_sel = c2.date_input("Fecha", value=date.today())

# Día de la semana
dias_esp = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}
nombre_dia = dias_esp.get(fecha_sel.weekday())

if df_h is not None:
    bloques = df_h[df_h["aula"] == aula_sel].drop_duplicates("hora_t").sort_values("hi")
    
    for _, b in bloques.iterrows():
        tipo, texto = "libre", "Disponible"
        
        # Verificar Clase
        c_m = df_h[(df_h["aula"] == aula_sel) & (df_h["dia"] == nombre_dia) & (df_h["hora_t"] == b["hora_t"]) & (df_h["tipo"] == "clase")]
        
        if not c_m.empty:
            tipo, texto = "clase", c_m.iloc[0]["desc"]
        else:
            # Verificar Reserva
            if not df_r.empty:
                r_m = df_r[(df_r["aula"] == aula_sel) & (df_r["f_dt"] == fecha_sel)]
                for _, r in r_m.iterrows():
                    if (b["hi"] < r["hf_dt"]) and (r["hi_dt"] < b["hf"]):
                        tipo, texto = "reserva", f"RESERVA: {r['user']}"
                        break
        
        # Mostrar bloque (Sintaxis simplificada para evitar errores)
        st.markdown(f"<div class='b {tipo}'><b>{b['hora_t']}</b> - {texto}</div>", unsafe_allow_html=True)

with st.expander("Depuración"):
    st.write("Reservas en sistema:", len(df_r))
    st.dataframe(df_r)
