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

# ─── FUNCIONES DE LIMPIEZA RADICAL ────────────────────────────────────────────
def normalizar_texto(txt):
    """Elimina espacios, guiones y convierte a mayúsculas para comparar sin fallos."""
    if pd.isna(txt): return ""
    return "".join(filter(str.isalnum, str(txt))).upper()

@st.cache_data(ttl=30)
def cargar_reservas():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
    try:
        response = requests.get(url)
        lines = response.content.decode('utf-8').splitlines()
        # Buscar dónde empieza la tabla real saltando la 'f' inicial
        for i, line in enumerate(lines):
            if "Marca temporal" in line:
                df = pd.read_csv(io.StringIO("\n".join(lines[i:])))
                break
        
        # Mapeo por posición de columna (esto no falla aunque cambien el nombre)
        # 3:Nombre | 4:Actividad | 6:Fecha | 7:Instalación | 8:Inicio | 9:Fin
        df_limpio = pd.DataFrame()
        df_limpio['nombre'] = df.iloc[:, 3]
        df_limpio['actividad'] = df.iloc[:, 4]
        df_limpio['fecha'] = df.iloc[:, 6]
        df_limpio['aula_id'] = df.iloc[:, 7].apply(normalizar_texto)
        df_limpio['h_ini'] = df.iloc[:, 8]
        df_limpio['h_fin'] = df.iloc[:, 9]
        return df_limpio
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
        for _, row in df_raw.iterrows():
            h_str = str(row["Hora"]).replace("–", "-").strip()
            try:
                p = h_str.split("-")
                h_ini = datetime.strptime(p[0].strip(), "%H:%M").time()
                h_fin = datetime.strptime(p[1].strip(), "%H:%M").time()
                for aula in [c for c in df_raw.columns if c not in ["Dia", "Hora"]]:
                    val = row[aula]
                    ocupado = not (pd.isna(val) or str(val).strip() == "")
                    filas.append({
                        "Dia": str(row["Dia"]).strip(),
                        "Hora": h_str, "H_Ini": h_ini, "H_Fin": h_fin,
                        "AulaID": normalizar_texto(aula),
                        "Detalle": str(val).strip() if ocupado else "Libre",
                        "Ocupada": ocupado
                    })
            except: continue
        return pd.DataFrame(filas)
    except: return None

# ─── APLICACIÓN ───────────────────────────────────────────────────────────────
df_h = cargar_horario()
df_r = cargar_reservas()

st.title("🔍 Disponibilidad UPES")

aula_sel = st.selectbox("Instalación", ["A-11", "A-12", "A-13", "A-14", "A-15", "A-16", "A-21 C/ACONDICIONADO", "A-22 C/ACONDICIONADO", "SUM", "BIBLIOTECA"])
fecha_sel = st.date_input("Fecha", value=date.today())

dias = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}

if df_h is not None:
    id_buscado = normalizar_texto(aula_sel)
    dia_buscado = dias[fecha_sel.weekday()]
    
    bloques = df_h[(df_h["AulaID"] == id_buscado) & (df_h["Dia"] == dia_buscado)]
    
    for _, row in bloques.iterrows():
        tipo, icono, detalle = ("clase", "🔴", row["Detalle"]) if row["Ocupada"] else ("libre", "✅", "Libre")
        
        # VALIDAR RESERVAS
        if not row["Ocupada"] and df_r is not None:
            for _, res in df_r.iterrows():
                try:
                    # Fecha flexible
                    r_fecha = pd.to_datetime(res['fecha']).date()
                    # Aula ID (A21CACONDICIONADO == A21CACONDICIONADO)
                    if r_fecha == fecha_sel and res['aula_id'] == id_buscado:
                        # Hora sin segundos
                        h_res_ini = datetime.strptime(str(res['h_ini'])[:5], "%H:%M").time()
                        h_res_fin = datetime.strptime(str(res['h_fin'])[:5], "%H:%M").time()
                        
                        if row["H_Ini"] < h_res_fin and h_res_ini < row["H_Fin"]:
                            tipo, icono = "reserva", "🟡"
                            detalle = f"RESERVA: {res['actividad']} ({res['nombre']})"
                            break
                except: continue

        st.markdown(f'<div class="bloque-item bloque-{tipo}"><span class="time-text">{icono} {row["Hora"]}</span>{detalle}</div>', unsafe_allow_html=True)
