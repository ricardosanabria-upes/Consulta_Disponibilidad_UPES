import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

st.set_page_config(page_title="UPES - Sistema de Disponibilidad", layout="wide")

st.markdown("""
<style>
    .bloque { padding: 10px; border-radius: 5px; margin-bottom: 5px; border: 1px solid #ccc; font-family: sans-serif; }
    .clase { background-color: #f8d7da; color: #721c24; border-left: 5px solid #dc3545; }
    .libre { background-color: #d4edda; color: #155724; border-left: 5px solid #28a745; }
    .reserva { background-color: #fff3cd; color: #856404; border-left: 5px solid #ffc107; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

def limpiar_id(t):
    if pd.isna(t): return ""
    return "".join(filter(str.isalnum, str(t))).upper()

@st.cache_data(ttl=10)
def cargar_datos():
    # 1. RESERVAS
    url_res = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
    try:
        res_raw = requests.get(url_res).text.splitlines()
        start_row = 0
        for i, line in enumerate(res_raw):
            if "Marca temporal" in line:
                start_row = i
                break
        df_res = pd.read_csv(io.StringIO("\n".join(res_raw[start_row:])))
        
        reservas = pd.DataFrame()
        reservas['actividad'] = df_res.iloc[:, 4]
        # PARSEO FLEXIBLE DE FECHA: Intenta Día/Mes/Año primero, si falla usa el del sistema
        reservas['fecha'] = pd.to_datetime(df_res.iloc[:, 6], dayfirst=True, errors='coerce').dt.date
        reservas['aula_id'] = df_res.iloc[:, 7].apply(limpiar_id)
        reservas['h_ini'] = df_res.iloc[:, 8].astype(str)
        reservas['h_fin'] = df_res.iloc[:, 9].astype(str)
        reservas['nombre'] = df_res.iloc[:, 3]
    except:
        reservas = pd.DataFrame()

    # 2. HORARIO
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
                        "AulaID": limpiar_id(aula),
                        "Detalle": str(val).strip() if ocupado else "Libre",
                        "Ocupado": ocupado
                    })
            except: continue
        horario = pd.DataFrame(horario_lista)
    except:
        horario = pd.DataFrame()

    return reservas, horario

df_r, df_h = cargar_datos()

st.title("Sistema de Disponibilidad UPES")

aula_sel = st.selectbox("Seleccione Aula", ["A-11", "A-12", "A-14", "A-21 C/Acondicionado", "A-22 C/Acondicionado", "A-32", "A-34 (Mesas de dibujo)", "SUM", "BIBLIOTECA"])
fecha_sel = st.date_input("Seleccione Fecha", value=date.today())

dias_map = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}
dia_nombre = dias_map[fecha_sel.weekday()]

if not df_h.empty:
    id_buscado = limpiar_id(aula_sel)
    bloques = df_h[(df_h["AulaID"] == id_buscado) & (df_h["Dia"] == dia_nombre)]
    
    st.subheader(f"Estado de {aula_sel} - {fecha_sel.strftime('%d/%m/%Y')}")
    
    for _, row in bloques.iterrows():
        tipo = "clase" if row["Ocupado"] else "libre"
        detalle = row["Detalle"]
        icono = "🔴" if row["Ocupado"] else "✅"
        
        # CRUZAR CON RESERVAS
        if not row["Ocupado"] and not df_r.empty:
            # Buscamos coincidencias de fecha y aula
            match = df_r[(df_r['fecha'] == fecha_sel) & (df_r['aula_id'] == id_buscado)]
            
            for _, res in match.iterrows():
                try:
                    # Limpiar las horas de la reserva (ej: "8:00:00" -> "08:00")
                    r_ini_str = res['h_ini'].strip().split()[0] # Por si trae AM/PM
                    r_fin_str = res['h_fin'].strip().split()[0]
                    
                    # Convertir a objeto time (tomando solo HH:MM)
                    res_ini = datetime.strptime(":".join(r_ini_str.split(":")[:2]), "%H:%M").time()
                    res_fin = datetime.strptime(":".join(r_fin_str.split(":")[:2]), "%H:%M").time()
                    
                    if row["H_Ini"] < res_fin and res_ini < row["H_Fin"]:
                        tipo = "reserva"
                        detalle = f"RESERVA: {res['actividad']} ({res['nombre']})"
                        icono = "🟡"
                        break
                except: continue

        st.markdown(f'<div class="bloque {tipo}"><b>{icono} {row["HoraStr"]}</b> - {detalle}</div>', unsafe_allow_html=True)

with st.expander("DEBUG: Información del Sistema"):
    st.write("Fecha buscada hoy:", fecha_sel)
    st.write("Reservas encontradas para esta fecha y aula:", len(df_r[(df_r['fecha'] == fecha_sel) & (df_r['aula_id'] == id_buscado)]))
    st.dataframe(df_r.head(10))
