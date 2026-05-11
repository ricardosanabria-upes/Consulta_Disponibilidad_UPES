import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="UPES - Disponibilidad", layout="wide")

st.markdown("""
<style>
    .bloque-item { padding: 12px; border-radius: 8px; margin-bottom: 5px; display: flex; align-items: center; border: 1px solid #ddd; }
    .bloque-clase { background-color: #ffebee; color: #b71c1c; border-left: 5px solid #b71c1c; }
    .bloque-libre { background-color: #e8f5e9; color: #1b5e20; border-left: 5px solid #1b5e20; }
    .bloque-reserva { background-color: #fff9c4; color: #827717; border-left: 5px solid #fbc02d; }
    .time-text { font-weight: bold; margin-right: 15px; width: 100px; }
</style>
""", unsafe_allow_html=True)

def simplificar(texto):
    """Convierte cualquier nombre de aula en un ID limpio (ej: 'A-21' -> 'A21')"""
    if pd.isna(texto): return ""
    return "".join(filter(str.isalnum, str(texto))).upper()

def convertir_hora(valor):
    """Convierte cualquier formato de hora (08:00:00 o 8:00 AM) a objeto time."""
    try:
        if isinstance(valor, datetime): return valor.time()
        # Intentar formatos comunes
        for formato in ["%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M%p"]:
            try:
                return datetime.strptime(str(valor).strip(), formato).time()
            except: continue
        return None
    except: return None

@st.cache_data(ttl=10)
def cargar_reservas():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
    try:
        response = requests.get(url)
        lineas = response.text.splitlines()
        
        # Ignorar basura inicial hasta encontrar los encabezados
        start_row = 0
        for i, line in enumerate(lineas):
            if "Marca temporal" in line:
                start_row = i
                break
        
        df = pd.read_csv(io.StringIO("\n".join(lineas[start_row:])))
        
        # Mapeo manual por POSICIÓN (Índices fijos según tu archivo real)
        # Col 3: Solicitante | Col 4: Actividad | Col 6: Fecha | Col 7: Aula | Col 8: Inicio | Col 9: Fin
        res = pd.DataFrame()
        res['nombre'] = df.iloc[:, 3]
        res['actividad'] = df.iloc[:, 4]
        res['fecha'] = pd.to_datetime(df.iloc[:, 6], errors='coerce').dt.date
        res['aula_id'] = df.iloc[:, 7].apply(simplificar)
        res['h_ini'] = df.iloc[:, 8].apply(convertir_hora)
        res['h_fin'] = df.iloc[:, 9].apply(convertir_hora)
        return res.dropna(subset=['fecha', 'h_ini', 'aula_id'])
    except: return None

@st.cache_data(ttl=3600)
def cargar_horario():
    url = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"
    try:
        resp = requests.get(url)
        df_raw = pd.read_excel(io.BytesIO(resp.content))
        df_raw["Dia"] = df_raw["Dia"].ffill()
        df_raw["Hora"] = df_raw["Hora"].ffill()
        
        filas = []
        aulas_col = [c for c in df_raw.columns if c not in ["Dia", "Hora"]]
        for _, row in df_raw.iterrows():
            h_str = str(row["Hora"]).replace("–", "-").strip()
            try:
                partes = h_str.split("-")
                h_ini = datetime.strptime(partes[0].strip(), "%H:%M").time()
                h_fin = datetime.strptime(partes[1].strip(), "%H:%M").time()
                for a in aulas_col:
                    val = row[a]
                    ocupado = not (pd.isna(val) or str(val).strip() == "")
                    filas.append({
                        "Dia": str(row["Dia"]).strip(),
                        "Hora": h_str, "H_Ini": h_ini, "H_Fin": h_fin,
                        "AulaID": simplificar(a),
                        "Detalle": str(val).strip() if ocupado else "Libre",
                        "Ocupada": ocupado
                    })
            except: continue
        return pd.DataFrame(filas)
    except: return None

# --- UI ---
df_h = cargar_horario()
df_r = cargar_reservas()

st.title("🔍 Disponibilidad de Instalaciones")

aula_sel = st.selectbox("Seleccione Instalación", ["A-11", "A-12", "A-13", "A-14", "A-15", "A-16", "A-21 C/ACONDICIONADO", "A-22 C/ACONDICIONADO", "SUM", "BIBLIOTECA"])
fecha_sel = st.date_input("Fecha de consulta", value=date.today())

dias_dic = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}

if df_h is not None:
    id_buscado = simplificar(aula_sel)
    dia_buscado = dias_dic[fecha_sel.weekday()]
    
    bloques = df_h[(df_h["AulaID"] == id_buscado) & (df_h["Dia"] == dia_buscado)]
    
    st.subheader(f"Estado de {aula_sel}")

    for _, row in bloques.iterrows():
        tipo, icono, detalle = ("clase", "🔴", row["Detalle"]) if row["Ocupada"] else ("libre", "✅", "Libre")
        
        # CRUCE CON RESERVAS
        if not row["Ocupada"] and df_r is not None:
            for _, res in df_r.iterrows():
                if res['fecha'] == fecha_sel and res['aula_id'] == id_buscado:
                    # Comparar objetos de tiempo directamente
                    if row["H_Ini"] < res['h_fin'] and res['h_ini'] < row["H_Fin"]:
                        tipo, icono = "reserva", "🟡"
                        detalle = f"RESERVA: {res['actividad']} ({res['nombre']})"
                        break

        st.markdown(f'<div class="bloque-item bloque-{tipo}"><span class="time-text">{icono} {row["Hora"]}</span>{detalle}</div>', unsafe_allow_html=True)
