import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

# --- CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="UPES - Disponibilidad", layout="wide")

st.markdown("""
<style>
    .bloque-item { padding: 15px; border-radius: 10px; margin-bottom: 8px; display: flex; align-items: center; border: 1px solid #ddd; }
    .bloque-clase { background-color: #ffebee; color: #b71c1c; border-left: 6px solid #b71c1c; }
    .bloque-libre { background-color: #e8f5e9; color: #1b5e20; border-left: 6px solid #1b5e20; }
    .bloque-reserva { background-color: #fff9c4; color: #827717; border-left: 6px solid #fbc02d; }
    .time-text { font-weight: bold; margin-right: 15px; width: 110px; font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)

def simplificar_aula(txt):
    """Normaliza nombres para que 'A-11' coincida con 'A 11' o 'a-11'"""
    if pd.isna(txt): return ""
    return "".join(filter(str.isalnum, str(txt))).upper()

@st.cache_data(ttl=30)
def cargar_reservas():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
    try:
        response = requests.get(url)
        content = response.content.decode('utf-8').splitlines()
        
        # Encontrar la fila donde empiezan los datos reales
        start_idx = 0
        for i, line in enumerate(content):
            if "Marca temporal" in line:
                start_idx = i
                break
        
        df = pd.read_csv(io.StringIO("\n".join(content[start_idx:])))
        
        # MAPEO POR POSICIÓN (Basado exactamente en tu archivo CSV)
        # Col 3: Solicitante | Col 4: Actividad | Col 6: Fecha | Col 7: Instalación | Col 8: Inicio | Col 9: Fin
        res_limpio = pd.DataFrame()
        res_limpio['nombre'] = df.iloc[:, 3]
        res_limpio['actividad'] = df.iloc[:, 4]
        res_limpio['fecha_raw'] = df.iloc[:, 6]
        res_limpio['aula_id'] = df.iloc[:, 7].apply(simplificar_aula)
        res_limpio['h_ini_raw'] = df.iloc[:, 8]
        res_limpio['h_fin_raw'] = df.iloc[:, 9]
        
        return res_limpio
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
                h_ini = datetime.strptime(h_str.split("-")[0].strip(), "%H:%M").time()
                h_fin = datetime.strptime(h_str.split("-")[1].strip(), "%H:%M").time()
                for aula in [c for c in df_raw.columns if c not in ["Dia", "Hora"]]:
                    val = row[aula]
                    ocupado = not (pd.isna(val) or str(val).strip() == "")
                    filas.append({
                        "Dia": str(row["Dia"]).strip(),
                        "Hora": h_str, "H_Ini": h_ini, "H_Fin": h_fin,
                        "AulaID": simplificar_aula(aula),
                        "Detalle": str(val).strip() if ocupado else "Libre",
                        "Ocupada": ocupado
                    })
            except: continue
        return pd.DataFrame(filas)
    except: return None

# --- LÓGICA PRINCIPAL ---
df_h = cargar_horario()
df_r = cargar_reservas()

st.title("🔍 Sistema de Disponibilidad UPES")

aula_sel = st.selectbox("Seleccione Instalación", ["A-11", "A-12", "A-13", "A-14", "A-15", "A-16", "A-21 C/ACONDICIONADO", "A-22 C/ACONDICIONADO", "SUM", "BIBLIOTECA"])
fecha_sel = st.date_input("Seleccione Fecha", value=date.today())

dias_map = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}

if df_h is not None:
    id_buscado = simplificar_aula(aula_sel)
    dia_buscado = dias_map[fecha_sel.weekday()]
    
    bloques = df_h[(df_h["AulaID"] == id_buscado) & (df_h["Dia"] == dia_buscado)]
    
    st.subheader(f"Estado para {aula_sel} el {fecha_sel.strftime('%d/%m/%Y')}")

    for _, row in bloques.iterrows():
        tipo, icono, detalle = ("clase", "🔴", row["Detalle"]) if row["Ocupada"] else ("libre", "✅", "Libre")
        
        # VALIDAR CONTRA LAS RESERVAS DE GOOGLE SHEETS
        if not row["Ocupada"] and df_r is not None:
            for _, res in df_r.iterrows():
                try:
                    # 1. Validar Fecha
                    f_res = pd.to_datetime(res['fecha_raw']).date()
                    
                    # 2. Validar Aula (Simplificado para ignorar espacios/guiones)
                    if f_res == fecha_sel and res['aula_id'] == id_buscado:
                        
                        # 3. Validar Hora (Cortamos los segundos del CSV :00:00)
                        h_ini_res = datetime.strptime(str(res['h_ini_raw'])[:5], "%H:%M").time()
                        h_fin_res = datetime.strptime(str(res['h_fin_raw'])[:5], "%H:%M").time()
                        
                        if row["H_Ini"] < h_fin_res and h_ini_res < row["H_Fin"]:
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
