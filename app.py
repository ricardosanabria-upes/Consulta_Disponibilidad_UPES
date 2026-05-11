import streamlit as st
import pandas as pd
import io
from datetime import datetime, date

# 1. Configuración de página
st.set_page_config(page_title="UPES", layout="wide")

# Estilos CSS ultra-seguros (sin líneas largas)
st.markdown("<style>.c {padding:10px;margin:5px;border-radius:8px;border:1px solid #ddd;} .libre{background:#f0fdf4;} .clase{background:#fef2f2;} .reserva{background:#fff9db;}</style>", unsafe_allow_html=True)

URL_SHEETS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
URL_GITHUB = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"

# 2. Carga de Reservas (Google Sheets)
@st.cache_data(ttl=60)
def cargar_reservas():
    try:
        # Cargamos saltando la fila de título
        df_raw = pd.read_csv(URL_SHEETS, skiprows=1)
        
        # CREAMOS UN DATAFRAME NUEVO SOLO CON LAS POSICIONES (No nombres)
        # Columna 3: Nombre, Columna 6: Fecha, Columna 7: Aula, Columna 8: Inicio, Columna 9: Fin
        df = pd.DataFrame()
        df['usuario'] = df_raw.iloc[:, 3].astype(str)
        df['fecha'] = df_raw.iloc[:, 6].astype(str)
        df['aula'] = df_raw.iloc[:, 7].astype(str).str.strip()
        df['inicio'] = df_raw.iloc[:, 8].astype(str)
        df['fin'] = df_raw.iloc[:, 9].astype(str)

        # Limpieza de nombres de aula
        df['aula'] = df['aula'].replace({"A-21": "A-21 C/Acondicionado", "A-22": "A-22 C/Acondicionado"})

        # Conversión segura de fechas y horas
        df['f_dt'] = pd.to_datetime(df['fecha'], dayfirst=True, errors='coerce').dt.date
        df['hi_dt'] = pd.to_datetime(df['inicio'], errors='coerce').dt.time
        df['hf_dt'] = pd.to_datetime(df['fin'], errors='coerce').dt.time
        
        return df.dropna(subset=['f_dt', 'hi_dt'])
    except:
        return pd.DataFrame()

# 3. Carga de Horario (GitHub)
@st.cache_data(ttl=3600)
def cargar_horario():
    try:
        import requests
        r = requests.get(URL_GITHUB)
        raw = pd.read_excel(io.BytesIO(r.content))
        raw["Dia"] = raw["Dia"].ffill()
        raw["Hora"] = raw["Hora"].ffill()
        
        datos = []
        aulas = [c for c in raw.columns if c not in ["Dia", "Hora"]]
        for _, fila in raw.iterrows():
            try:
                h_txt = str(fila["Hora"]).replace("–", "-")
                hi = datetime.strptime(h_txt.split("-")[0].strip(), "%H:%M").time()
                hf = datetime.strptime(h_txt.split("-")[1].strip(), "%H:%M").time()
                for a in aulas:
                    val = str(fila[a]).strip()
                    ocupado = val != "" and val.lower() != "nan"
                    datos.append({
                        "dia": str(fila["Dia"]), "hora_t": h_txt, "hi": hi, "hf": hf,
                        "aula": a.strip(), "info": val if ocupado else "Disponible", 
                        "tipo": "clase" if ocupado else "libre"
                    })
            except: continue
        return pd.DataFrame(datos)
    except: return None

# 4. Interfaz
st.title("🏫 Control de Instalaciones UPES")

df_h = cargar_horario()
df_r = cargar_reservas()

if df_h is not None:
    # Selectores
    lista_aulas = sorted(df_h["aula"].unique())
    c1, c2 = st.columns(2)
    aula_sel = c1.selectbox("Aula", lista_aulas)
    fecha_sel = c2.date_input("Fecha", value=date.today())

    # Día en español
    dias = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}
    dia_txt = dias.get(fecha_sel.weekday())

    # Bloques del aula
    bloques = df_h[df_h["aula"] == aula_sel].drop_duplicates("hora_t").sort_values("hi")

    for _, b in bloques.iterrows():
        tipo, texto = "libre", "Disponible"
        
        # 1. ¿Es clase fija?
        m_c = df_h[(df_h["aula"] == aula_sel) & (df_h["dia"] == dia_txt) & (df_h["hora_t"] == b["hora_t"]) & (df_h["tipo"] == "clase")]
        
        if not m_c.empty:
            tipo, texto = "clase", m_c.iloc[0]["info"]
        else:
            # 2. ¿Es reserva de Google Sheets?
            if not df_r.empty:
                m_r = df_r[(df_r["aula"] == aula_sel) & (df_r["f_dt"] == fecha_sel)]
                for _, r in m_r.iterrows():
                    if (b["hi"] < r["hf_dt"]) and (r["hi_dt"] < b["hf"]):
                        tipo, texto = "reserva", f"RESERVA: {r['usuario']}"
                        break
        
        # Mostrar bloque
        st.markdown(f"<div class='c {tipo}'><b>{b['hora_t']}</b> - {texto}</div>", unsafe_allow_html=True)

# Depuración para confirmar que los datos entran
with st.expander("Verificar conexión de datos"):
    st.write("Reservas detectadas en la nube:", len(df_r))
    st.dataframe(df_r)
