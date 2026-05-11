import streamlit as st
import pandas as pd
import io
from datetime import datetime, date, time

# 1. Configuración Básica
st.set_page_config(page_title="UPES Disponibilidad", layout="wide")

st.markdown("""
<style>
    .libre   { background:#f0fdf4; border:1px solid #86efac; border-radius:10px; padding:10px; margin:5px 0; color:#166534; }
    .clase   { background:#fef2f2; border:1px solid #fca5a5; border-radius:10px; padding:10px; margin:5px 0; color:#991b1b; }
    .reserva { background:#fff9db; border:1px solid #fcc419; border-radius:10px; padding:10px; margin:5px 0; color:#856404; }
</style>
""", unsafe_allow_html=True)

# 2. Enlaces
URL_SHEETS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
URL_GITHUB = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"

INSTALACIONES = [
    "A-11", "A-12", "A-13", "A-14", "A-15", "A-16",
    "A-21 C/Acondicionado", "A-22 C/Acondicionado",
    "A-31", "A-32", "A-33", "A-34 (Mesas de dibujo)", "A-35", "A-36",
    "A-41", "A-42", "A-43", "A-44", "A-45", "A-46",
    "SUM", "Sala de juntas", "Pasillos", "Biblioteca"
]

# 3. Carga de Datos de Google Sheets (Búsqueda por palabras clave)
@st.cache_data(ttl=60)
def cargar_reservas():
    try:
        # Forzar lectura ignorando errores de formato inicial
        df = pd.read_csv(URL_SHEETS, skiprows=1)
        df.columns = [str(c).replace('\n', ' ').strip() for c in df.columns]
        
        # Mapa para encontrar columnas críticas sin importar el nombre exacto
        mapeo = {}
        for col in df.columns:
            c = col.lower()
            if "instalación" in c or "instalacion" in c: mapeo[col] = "aula"
            elif "fecha" in c: mapeo[col] = "fecha"
            elif "inicio" in c: mapeo[col] = "h_ini"
            elif "finalización" in c or "finalizacion" in c: mapeo[col] = "h_fin"
            elif "solicitante" in c: mapeo[col] = "nombre"
        
        df = df.rename(columns=mapeo)
        
        # Asegurar que existan las columnas mínimas
        for col_nec in ["aula", "fecha", "h_ini", "h_fin"]:
            if col_nec not in df.columns: return pd.DataFrame()

        # Limpiar Aulas (Compatibilidad con el formulario)
        df["aula"] = df["aula"].astype(str).str.strip()
        df["aula"] = df["aula"].replace({"A-21": "A-21 C/Acondicionado", "A-22": "A-22 C/Acondicionado", "A-34": "A-34 (Mesas de dibujo)"})

        # Convertir tiempos
        df["fecha_dt"] = pd.to_datetime(df["fecha"], dayfirst=True, errors='coerce').dt.date
        df["h_ini_dt"] = pd.to_datetime(df["h_ini"], errors='coerce').dt.time
        df["h_fin_dt"] = pd.to_datetime(df["h_fin"], errors='coerce').dt.time
        
        return df.dropna(subset=["aula", "fecha_dt", "h_ini_dt"])
    except:
        return pd.DataFrame()

# 4. Carga de Horario GitHub
@st.cache_data(ttl=3600)
def cargar_horario():
    try:
        import requests
        r = requests.get(URL_GITHUB)
        df_raw = pd.read_excel(io.BytesIO(r.content))
        df_raw["Dia"] = df_raw["Dia"].ffill()
        df_raw["Hora"] = df_raw["Hora"].ffill()
        
        lista = []
        aulas = [c for c in df_raw.columns if c not in ["Dia", "Hora"]]
        for _, row in df_raw.iterrows():
            try:
                h_txt = str(row["Hora"]).replace("–", "-")
                h_ini = datetime.strptime(h_txt.split("-")[0].strip(), "%H:%M").time()
                h_fin = datetime.strptime(h_txt.split("-")[1].strip(), "%H:%M").time()
                for a in aulas:
                    val = str(row[a]).strip()
                    es_clase = val != "" and val.lower() != "nan"
                    lista.append({
                        "dia": str(row["Dia"]), "hora_t": h_txt, "hi": h_ini, "hf": h_fin,
                        "aula": a.strip(), "detalle": val if es_clase else "Disponible", "tipo": "clase" if es_clase else "libre"
                    })
            except: continue
        return pd.DataFrame(lista)
    except: return None

# 5. Interfaz y Lógica de Bloques
st.title("🏫 Sistema de Disponibilidad UPES")

df_h = cargar_horario()
df_r = cargar_reservas()

c1, c2 = st.columns(2)
aula_sel = c1.selectbox("Aula", INSTALACIONES)
fecha_sel = c2.date_input("Fecha", value=date.today())

DIAS = {0: "1.Lunes", 1: "2.Martes", 2: "3.Miercoles", 3: "4.Jueves", 4: "5.Viernes", 5: "6.Sabado", 6: "7.Domingo"}
dia_nombre = DIAS.get(fecha_sel.weekday())

if df_h is not None:
    # Bloques de tiempo fijos para esta aula
    bloques = df_h[df_h["aula"].str.contains(aula_sel.split()[0])].drop_duplicates(subset=["hora_t"]).sort_values("hi")
    
    for _, b in bloques.iterrows():
        est = "libre"
        det = "Disponible"
        
        # Prioridad 1: Clase
        match_c = df_h[(df_h["aula"].str.contains(aula_sel.split()[0])) & (df_h["dia"] == dia_nombre) & (df_h["hora_t"] == b["hora_t"]) & (df_h["tipo"] == "clase")]
        if not match_c.empty:
            est, det = "clase", match_c.iloc[0]["detalle"]
        else:
            # Prioridad 2: Reserva
            if not df_r.empty:
                m_res = df_r[(df_r["aula"] == aula_sel) & (df_r["fecha_dt"] == fecha_sel)]
                for _, r in m_res.iterrows():
                    if (b["hi"] < r["h_fin_dt"]) and (r["h_ini_dt"] < b["hf"]):
                        est, det = "reserva", f"RESERVA: {r.get('nombre', 'Solicitante')}"
                        break
        
        st.markdown(f"<div class='{est}'><b>{b['hora_t']}</b> — {det}</div>", unsafe_allow_html=True)

with st.expander("Ver Datos Crudos (Debug)"):
    st.write("Reservas detectadas:", len(df_r))
    st.dataframe(df_r)
