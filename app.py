import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

# ─── CONFIGURACIÓN VISUAL ─────────────────────────────────────────────────────
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

# ─── LIMPIEZA DE DATOS (MÉTODO RADICAL) ───────────────────────────────────────
def simplificar_texto(txt):
    """Elimina todo lo que no sea letras o números para comparar A-11 con A11."""
    if pd.isna(txt): return ""
    return "".join(filter(str.isalnum, str(txt))).upper()

@st.cache_data(ttl=30)
def cargar_reservas():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
    try:
        response = requests.get(url)
        content = response.content.decode('utf-8').splitlines()
        
        # Saltar cualquier basura inicial hasta encontrar "Marca temporal"
        start_line = 0
        for i, line in enumerate(content):
            if "Marca temporal" in line:
                start_line = i
                break
        
        # Leer el CSV ignorando los nombres de columnas problemáticos
        df = pd.read_csv(io.StringIO("\n".join(content[start_line:])))
        
        # MAPEO POR POSICIÓN (Índices fijos basados en tu archivo real):
        # Col 3: Solicitante | Col 4: Actividad | Col 6: Fecha | Col 7: Instalación | Col 8: Inicio | Col 9: Fin
        df_limpio = pd.DataFrame()
        df_limpio['nombre'] = df.iloc[:, 3]
        df_limpio['actividad'] = df.iloc[:, 4]
        df_limpio['fecha'] = df.iloc[:, 6]
        df_limpio['aula_id'] = df.iloc[:, 7].apply(simplificar_texto)
        df_limpio['h_ini'] = df.iloc[:, 8]
        df_limpio['h_fin'] = df.iloc[:, 9]
        
        return df_limpio
    except Exception as e:
        st.error(f"Error cargando Sheet: {e}")
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
        for _, row in df_raw.iterrows():
            h_raw = str(row["Hora"]).replace("–", "-").strip()
            try:
                p = h_raw.split("-")
                h_ini = datetime.strptime(p[0].strip(), "%H:%M").time()
                h_fin = datetime.strptime(p[1].strip(), "%H:%M").time()
                for col in [c for c in df_raw.columns if c not in ["Dia", "Hora"]]:
                    val = row[col]
                    ocupado = not (pd.isna(val) or str(val).strip() == "")
                    filas.append({
                        "Dia": str(row["Dia"]).strip(),
                        "Hora": h_raw, "H_Ini": h_ini, "H_Fin": h_fin,
                        "AulaNombre": str(col),
                        "AulaID": simplificar_texto(col),
                        "Detalle": str(val).strip() if ocupado else "Libre",
                        "Ocupada": ocupado
                    })
            except: continue
        return pd.DataFrame(filas)
    except: return None

# ─── LÓGICA DE APLICACIÓN ─────────────────────────────────────────────────────
df_h = cargar_horario()
df_r = cargar_reservas()

st.title("🔍 Disponibilidad de Aulas UPES")

# Selector con los nombres exactos que quieres mostrar
aulas_lista = ["A-11", "A-12", "A-13", "A-14", "A-15", "A-16", "A-21 C/ACONDICIONADO", "A-22 C/ACONDICIONADO", "A-31", "A-32", "A-33", "A-34 (MESAS DE DIBUJO)", "SUM", "BIBLIOTECA"]
aula_sel = st.selectbox("Seleccione la Instalación:", aulas_lista)
fecha_sel = st.date_input("Seleccione la Fecha:", value=date.today())

dia_semana = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}

if df_h is not None:
    id_buscado = simplificar_texto(aula_sel)
    dia_buscado = dia_semana[fecha_sel.weekday()]
    
    # Filtrar bloques del horario base (Excel)
    bloques = df_h[(df_h["AulaID"] == id_buscado) & (df_h["Dia"] == dia_buscado)]
    
    st.info(f"Mostrando horario para {aula_sel} el {fecha_sel.strftime('%d/%m/%Y')}")

    for _, row in bloques.iterrows():
        tipo, icono, detalle = ("clase", "🔴", row["Detalle"]) if row["Ocupada"] else ("libre", "✅", "Libre")
        
        # CRUCE CON RESERVAS (Google Sheets)
        if not row["Ocupada"] and df_r is not None:
            for _, res in df_r.iterrows():
                try:
                    # 1. Validar Fecha (Pandas detecta automáticamente YYYY-MM-DD o DD/MM/YYYY)
                    r_fecha = pd.to_datetime(res['fecha']).date()
                    
                    # 2. Validar Aula (Comparando IDs simplificados sin espacios ni guiones)
                    if r_fecha == fecha_sel and res['aula_id'] == id_buscado:
                        
                        # 3. Validar Horario (Cortando los segundos del CSV :00:00)
                        h_res_ini = datetime.strptime(str(res['h_ini'])[:5], "%H:%M").time()
                        h_res_fin = datetime.strptime(str(res['h_fin'])[:5], "%H:%M").time()
                        
                        if row["H_Ini"] < h_res_fin and h_res_ini < row["H_Fin"]:
                            tipo, icono = "reserva", "🟡"
                            detalle = f"RESERVA: {res['actividad']} ({res['nombre']})"
                            break
                except: continue

        st.markdown(f"""
            <div class="bloque-item bloque-{tipo}">
                <span class="time-text">{icono} {row['Hora']}</span>
                <span>{detalle}</span>
            </div>
        """, unsafe_allow_html=True)
