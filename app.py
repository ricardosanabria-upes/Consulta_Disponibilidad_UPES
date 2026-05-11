import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

st.set_page_config(page_title="UPES - Sistema de Disponibilidad", layout="wide")

# --- ESTILOS ---
st.markdown("""
<style>
    .bloque { padding: 10px; border-radius: 5px; margin-bottom: 5px; border: 1px solid #ccc; font-family: sans-serif; }
    .clase { background-color: #f8d7da; color: #721c24; border-left: 5px solid #dc3545; }
    .libre { background-color: #d4edda; color: #155724; border-left: 5px solid #28a745; }
    .reserva { background-color: #fff3cd; color: #856404; border-left: 5px solid #ffc107; }
</style>
""", unsafe_allow_html=True)

def limpiar_texto(t):
    if pd.isna(t): return ""
    return "".join(filter(str.isalnum, str(t))).upper()

@st.cache_data(ttl=10)
def cargar_datos():
    # 1. CARGAR RESERVAS (GOOGLE SHEETS)
    url_res = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
    try:
        res_raw = requests.get(url_res).text.splitlines()
        # Buscar la fila de encabezados real
        start_row = 0
        for i, line in enumerate(res_raw):
            if "Marca temporal" in line:
                start_row = i
                break
        df_res = pd.read_csv(io.StringIO("\n".join(res_raw[start_row:])))
        
        # Limpiar Columnas de Reservas usando POSICIÓN (según tu imagen)
        reservas = pd.DataFrame()
        reservas['actividad'] = df_res.iloc[:, 4] # Columna E
        reservas['fecha'] = pd.to_datetime(df_res.iloc[:, 6], dayfirst=True, errors='coerce').dt.date # Columna G
        reservas['aula_id'] = df_res.iloc[:, 7].apply(limpiar_texto) # Columna H
        reservas['h_ini'] = df_res.iloc[:, 8].astype(str).str.strip() # Columna I
        reservas['h_fin'] = df_res.iloc[:, 9].astype(str).str.strip() # Columna J
        reservas['nombre'] = df_res.iloc[:, 3] # Columna D
    except:
        reservas = pd.DataFrame()

    # 2. CARGAR HORARIO (GITHUB)
    url_hor = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"
    try:
        resp = requests.get(url_hor)
        df_hor = pd.read_excel(io.BytesIO(resp.content))
        df_hor["Dia"] = df_hor["Dia"].ffill()
        df_hor["Hora"] = df_hor["Hora"].ffill()
        
        horario_lista = []
        columnas_aulas = [c for c in df_hor.columns if c not in ["Dia", "Hora"]]
        for _, row in df_hor.iterrows():
            try:
                h_range = str(row["Hora"]).replace("–", "-").split("-")
                h_ini = datetime.strptime(h_range[0].strip(), "%H:%M").time()
                h_fin = datetime.strptime(h_range[1].strip(), "%H:%M").time()
                for aula in columnas_aulas:
                    val = row[aula]
                    ocupado = not (pd.isna(val) or str(val).strip() == "")
                    horario_lista.append({
                        "Dia": str(row["Dia"]).strip(),
                        "HoraStr": str(row["Hora"]),
                        "H_Ini": h_ini, "H_Fin": h_fin,
                        "AulaID": limpiar_texto(aula),
                        "Detalle": str(val).strip() if ocupado else "Libre",
                        "Ocupado": ocupado
                    })
            except: continue
        horario = pd.DataFrame(horario_lista)
    except:
        horario = pd.DataFrame()

    return reservas, horario

df_r, df_h = cargar_datos()

# --- INTERFAZ ---
st.title("Sistema de Disponibilidad UPES")

aulas_opciones = ["A-11", "A-12", "A-14", "A-21 C/Acondicionado", "A-22 C/Acondicionado", "A-32", "A-34 (Mesas de dibujo)", "SUM", "BIBLIOTECA"]
aula_sel = st.selectbox("Seleccione Aula", aulas_opciones)
fecha_sel = st.date_input("Seleccione Fecha", value=date.today())

dias_map = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}
dia_nombre = dias_map[fecha_sel.weekday()]

if not df_h.empty:
    id_buscado = limpiar_texto(aula_sel)
    # Filtrar clases del horario base
    bloques = df_h[(df_h["AulaID"] == id_buscado) & (df_h["Dia"] == dia_nombre)]
    
    st.subheader(f"Disponibilidad para {aula_sel} - {fecha_sel.strftime('%d/%m/%Y')}")
    
    for _, row in bloques.iterrows():
        tipo = "clase" if row["Ocupado"] else "libre"
        detalle = row["Detalle"]
        icono = "🔴" if row["Ocupado"] else "✅"
        
        # Verificar Reservas en bloques LIBRES
        if not row["Ocupado"] and not df_r.empty:
            # Filtro estricto de reserva
            match = df_r[
                (df_r['fecha'] == fecha_sel) & 
                (df_r['aula_id'] == id_buscado)
            ]
            
            for _, res in match.iterrows():
                try:
                    # Normalizar hora de reserva (quitar segundos si existen)
                    res_ini = datetime.strptime(res['h_ini'][:5], "%H:%M").time()
                    res_fin = datetime.strptime(res['h_fin'][:5], "%H:%M").time()
                    
                    # Si hay traslape
                    if row["H_Ini"] < res_fin and res_ini < row["H_Fin"]:
                        tipo = "reserva"
                        detalle = f"RESERVA: {res['actividad']} ({res['nombre']})"
                        icono = "🟡"
                        break
                except: continue

        st.markdown(f'<div class="bloque {tipo}"><b>{icono} {row["HoraStr"]}</b> - {detalle}</div>', unsafe_allow_html=True)

# --- SECCIÓN DE DEPURACIÓN (BORRAR DESPUÉS) ---
with st.expander("DEBUG: Ver qué está leyendo el sistema"):
    st.write("Día detectado:", dia_nombre)
    st.write("ID de Aula buscado:", id_buscado)
    st.write("Muestra de Reservas cargadas:", df_r.head())
