import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="UPES - Disponibilidad", layout="wide")

st.markdown("""
<style>
    .bloque-item { padding: 12px; border-radius: 8px; margin-bottom: 5px; display: flex; align-items: center; border: 1px solid #ddd; font-family: sans-serif; }
    .bloque-clase { background-color: #ffebee; color: #b71c1c; border-left: 5px solid #b71c1c; }
    .bloque-libre { background-color: #e8f5e9; color: #1b5e20; border-left: 5px solid #1b5e20; }
    .bloque-reserva { background-color: #fff9c4; color: #827717; border-left: 5px solid #fbc02d; }
    .time-text { font-weight: bold; margin-right: 15px; width: 100px; }
</style>
""", unsafe_allow_html=True)

def simplificar(texto):
    """Convierte 'A-21 C/ACONDICIONADO' en 'A21CACONDICIONADO' para comparar sin errores."""
    if pd.isna(texto): return ""
    return "".join(filter(str.isalnum, str(texto))).upper()

@st.cache_data(ttl=10)
def cargar_reservas():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
    try:
        response = requests.get(url)
        # Cargamos el archivo como texto puro para limpiar la fila 'f'
        lines = response.text.splitlines()
        start_line = 0
        for i, line in enumerate(lines):
            if "Marca temporal" in line:
                start_line = i
                break
        
        # Leemos el CSV desde la cabecera real
        df = pd.read_csv(io.StringIO("\n".join(lines[start_line:])))
        
        # MAPEO POR POSICIÓN (Basado exactamente en tu imagen)
        # Col 3: Solicitante | Col 4: Actividad | Col 6: Fecha | Col 7: Aula | Col 8: Inicio | Col 9: Fin
        df_limpio = pd.DataFrame()
        df_limpio['nombre'] = df.iloc[:, 3]
        df_limpio['actividad'] = df.iloc[:, 4]
        df_limpio['fecha'] = df.iloc[:, 6]
        df_limpio['aula_id'] = df.iloc[:, 7].apply(simplificar)
        df_limpio['h_ini'] = df.iloc[:, 8]
        df_limpio['h_fin'] = df.iloc[:, 9]
        return df_limpio
    except: return None

@st.cache_data(ttl=3600)
def cargar_horario():
    url = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"
    try:
        resp = requests.get(url)
        df = pd.read_excel(io.BytesIO(resp.content))
        df["Dia"] = df["Dia"].ffill()
        df["Hora"] = df["Hora"].ffill()
        
        filas = []
        aulas = [c for c in df.columns if c not in ["Dia", "Hora"]]
        for _, row in df.iterrows():
            h_str = str(row["Hora"]).replace("–", "-").strip()
            try:
                h_ini = datetime.strptime(h_str.split("-")[0].strip(), "%H:%M").time()
                h_fin = datetime.strptime(h_str.split("-")[1].strip(), "%H:%M").time()
                for a in aulas:
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

# --- UI PRINCIPAL ---
df_h = cargar_horario()
df_r = cargar_reservas()

st.title("🔍 Disponibilidad UPES")

# Lista de selección manual para el usuario
opciones_aulas = ["A-11", "A-12", "A-13", "A-14", "A-15", "A-16", "A-21 C/ACONDICIONADO", "A-22 C/ACONDICIONADO", "SUM", "BIBLIOTECA"]
aula_sel = st.selectbox("Seleccione Instalación", opciones_aulas)
fecha_sel = st.date_input("Seleccione Fecha", value=date.today())

dias_dic = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}

if df_h is not None:
    id_buscado = simplificar(aula_sel)
    dia_buscado = dias_dic[fecha_sel.weekday()]
    
    bloques = df_h[(df_h["AulaID"] == id_buscado) & (df_h["Dia"] == dia_buscado)]
    
    st.subheader(f"Estado de {aula_sel}")

    for _, row in bloques.iterrows():
        tipo, icono, detalle = ("clase", "🔴", row["Detalle"]) if row["Ocupada"] else ("libre", "✅", "Libre")
        
        # VALIDAR SI HAY RESERVA EN ESTE BLOQUE LIBRE
        if not row["Ocupada"] and df_r is not None:
            for _, res in df_r.iterrows():
                try:
                    # Normalizar fecha del CSV
                    r_fecha = pd.to_datetime(res['fecha']).date()
                    
                    # Comparar Fecha e ID de aula (simplificado)
                    if r_fecha == fecha_sel and res['aula_id'] == id_buscado:
                        # Limpiar horas (quitar segundos si los hay)
                        h_res_ini = datetime.strptime(str(res['h_ini'])[:5], "%H:%M").time()
                        h_res_fin = datetime.strptime(str(res['h_fin'])[:5], "%H:%M").time()
                        
                        # Comprobar traslape
                        if row["H_Ini"] < h_res_fin and h_res_ini < row["H_Fin"]:
                            tipo, icono = "reserva", "🟡"
                            detalle = f"RESERVA: {res['actividad']} ({res['nombre']})"
                            break
                except: continue

        st.markdown(f'<div class="bloque-item bloque-{tipo}"><span class="time-text">{icono} {row["Hora"]}</span>{detalle}</div>', unsafe_allow_html=True)
