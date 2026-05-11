import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

# ─── CONFIGURACIÓN VISUAL ─────────────────────────────────────────────────────
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

# ─── LIMPIEZA DE DATOS ────────────────────────────────────────────────────────
def simplificar(t):
    """Limpia todo para que 'A-21' sea igual a 'A21' independientemente de espacios."""
    if pd.isna(t): return ""
    return "".join(filter(str.isalnum, str(t))).upper()

@st.cache_data(ttl=10)
def cargar_reservas():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
    try:
        response = requests.get(url)
        # Leer el CSV crudo para detectar la cabecera real
        lines = response.text.splitlines()
        start_idx = 0
        for i, line in enumerate(lines):
            if "Marca temporal" in line:
                start_idx = i
                break
        
        df = pd.read_csv(io.StringIO("\n".join(lines[start_idx:])))
        
        # Mapeo por POSICIÓN (Índices fijos según el CSV de Google Forms habitual)
        # Col 3: Solicitante | Col 4: Actividad | Col 6: Fecha | Col 7: Instalación | Col 8: Inicio | Col 9: Fin
        res = pd.DataFrame()
        res['nombre'] = df.iloc[:, 3]
        res['actividad'] = df.iloc[:, 4]
        res['fecha_raw'] = df.iloc[:, 6]
        res['aula_id'] = df.iloc[:, 7].apply(simplificar)
        res['h_ini_raw'] = df.iloc[:, 8]
        res['h_fin_raw'] = df.iloc[:, 9]
        return res
    except:
        return None

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
                # Extraer tiempos del bloque de clase (Excel)
                h_ini = datetime.strptime(h_str.split("-")[0].strip(), "%H:%M").time()
                h_fin = datetime.strptime(h_str.split("-")[1].strip(), "%H:%M").time()
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

# ─── INTERFAZ Y LÓGICA ────────────────────────────────────────────────────────
df_h = cargar_horario()
df_r = cargar_reservas()

st.title("🔍 Sistema de Disponibilidad UPES")

# Selector con los nombres estándar
aulas_disponibles = ["A-11", "A-12", "A-13", "A-14", "A-15", "A-16", "A-21 C/ACONDICIONADO", "A-22 C/ACONDICIONADO", "SUM", "BIBLIOTECA"]
aula_sel = st.selectbox("Seleccione Aula", aulas_disponibles)
fecha_sel = st.date_input("Seleccione Fecha", value=date.today())

dias_map = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}

if df_h is not None:
    id_buscado = simplificar(aula_sel)
    dia_buscado = dias_map[fecha_sel.weekday()]
    
    bloques = df_h[(df_h["AulaID"] == id_buscado) & (df_h["Dia"] == dia_buscado)]
    
    st.subheader(f"Estado de {aula_sel}")

    for _, row in bloques.iterrows():
        tipo, icono, detalle = ("clase", "🔴", row["Detalle"]) if row["Ocupada"] else ("libre", "✅", "Libre")
        
        # VALIDAR CONTRA RESERVAS (GOOGLE SHEETS)
        if not row["Ocupada"] and df_r is not None:
            for _, res in df_r.iterrows():
                try:
                    # 1. Validar Fecha (Normalizada)
                    f_res = pd.to_datetime(res['fecha_raw']).date()
                    
                    if f_res == fecha_sel and res['aula_id'] == id_buscado:
                        # 2. Validar Hora (Eliminar segundos :00 del CSV)
                        h_res_ini = datetime.strptime(str(res['h_ini_raw'])[:5], "%H:%M").time()
                        h_res_fin = datetime.strptime(str(res['h_fin_raw'])[:5], "%H:%M").time()
                        
                        # Cruce de horarios
                        if row["H_Ini"] < h_res_fin and h_res_ini < row["H_Fin"]:
                            tipo, icono = "reserva", "🟡"
                            detalle = f"RESERVA: {res['actividad']} ({res['nombre']})"
                            break
                except: continue

        st.markdown(f'<div class="bloque-item bloque-{tipo}"><span class="time-text">{icono} {row["Hora"]}</span>{detalle}</div>', unsafe_allow_html=True)
