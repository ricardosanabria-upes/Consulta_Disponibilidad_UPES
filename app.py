import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

# ─── CONFIGURACIÓN DE PÁGINA ──────────────────────────────────────────────────
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

# ─── FUNCIÓN DE LIMPIEZA SUPREMA ──────────────────────────────────────────────
def limpiar_texto(t):
    """Elimina saltos de línea, espacios y guiones para que 'A-11' sea igual a 'A11'"""
    if pd.isna(t): return ""
    return "".join(filter(str.isalnum, str(t))).upper()

# ─── CARGA DE DATOS ───────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def cargar_reservas():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
    try:
        response = requests.get(url)
        lineas = response.content.decode('utf-8').splitlines()
        # Saltar la fila 'f' y buscar donde dice "Marca temporal"
        for i, fila in enumerate(lineas):
            if "Marca temporal" in fila:
                df = pd.read_csv(io.StringIO("\n".join(lineas[i:])))
                break
        
        # Mapeo por posición (Índices fijos de tu archivo)
        res = pd.DataFrame()
        res['nombre'] = df.iloc[:, 3]    # Solicitante
        res['actividad'] = df.iloc[:, 4] # Actividad
        res['fecha'] = df.iloc[:, 6]     # Fecha
        res['aula_id'] = df.iloc[:, 7].apply(limpiar_texto) # Instalación
        res['h_ini'] = df.iloc[:, 8]     # Inicio
        res['h_fin'] = df.iloc[:, 9]     # Fin
        return res
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
        # Columnas de aulas (saltando Dia y Hora)
        aulas_col = [c for c in df_raw.columns if c not in ["Dia", "Hora"]]
        for _, row in df_raw.iterrows():
            h_str = str(row["Hora"]).replace("–", "-").strip()
            try:
                h_ini = datetime.strptime(h_str.split("-")[0].strip(), "%H:%M").time()
                h_fin = datetime.strptime(h_str.split("-")[1].strip(), "%H:%M").time()
                for a in aulas_col:
                    val = row[a]
                    ocupado = not (pd.isna(val) or str(val).strip() == "")
                    filas.append({
                        "Dia": str(row["Dia"]).strip(),
                        "Hora": h_str, "H_Ini": h_ini, "H_Fin": h_fin,
                        "AulaOriginal": str(a),
                        "AulaID": limpiar_texto(a),
                        "Detalle": str(val).strip() if ocupado else "Libre",
                        "Ocupada": ocupado
                    })
            except: continue
        return pd.DataFrame(filas)
    except: return None

# ─── INTERFAZ ─────────────────────────────────────────────────────────────────
df_h = cargar_horario()
df_r = cargar_reservas()

st.title("🔍 Disponibilidad de Instalaciones UPES")

# Lista de aulas para el usuario
lista_aulas = ["A-11", "A-12", "A-13", "A-14", "A-15", "A-16", "A-21 C/ACONDICIONADO", "A-22 C/ACONDICIONADO", "A-31", "A-32", "A-33", "A-34 (MESAS DE DIBUJO)", "SUM", "BIBLIOTECA"]
aula_sel = st.selectbox("Seleccione Aula:", lista_aulas)
fecha_sel = st.date_input("Fecha:", value=date.today())

dias_dic = {0:"1.Lunes", 1:"2.Martes", 2:"3.Miercoles", 3:"4.Jueves", 4:"5.Viernes", 5:"6.Sabado", 6:"7.Domingo"}

if df_h is not None:
    id_buscado = limpiar_texto(aula_sel)
    dia_buscado = dias_dic[fecha_sel.weekday()]
    
    # Filtrar horario base
    bloques = df_h[(df_h["AulaID"] == id_buscado) & (df_h["Dia"] == dia_buscado)]
    
    st.subheader(f"Horario para {aula_sel}")

    for _, row in bloques.iterrows():
        tipo, icono, detalle = ("clase", "🔴", row["Detalle"]) if row["Ocupada"] else ("libre", "✅", "Libre")
        
        # CRUZAR CON RESERVAS
        if not row["Ocupada"] and df_r is not None:
            for _, res in df_r.iterrows():
                try:
                    # 1. Fecha (YYYY-MM-DD)
                    r_fecha = pd.to_datetime(res['fecha']).date()
                    # 2. Aula (ID Limpio)
                    if r_fecha == fecha_sel and res['aula_id'] == id_buscado:
                        # 3. Horas (Cortar segundos :00)
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
