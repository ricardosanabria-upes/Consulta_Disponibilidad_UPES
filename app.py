import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, date

# ─── CONFIGURACIÓN ───────────────────────────────────────────────────────────
st.set_page_config(page_title="UPES - Disponibilidad de Aulas", layout="wide")

st.markdown("""
<style>
    .bloque { padding: 15px; border-radius: 10px; margin-bottom: 8px; border: 1px solid #ddd; font-family: sans-serif; }
    .clase { background-color: #ffebee; color: #b71c1c; border-left: 6px solid #b71c1c; }
    .libre { background-color: #e8f5e9; color: #1b5e20; border-left: 6px solid #1b5e20; }
    .reserva { background-color: #fff9c4; color: #827717; border-left: 6px solid #fbc02d; font-weight: bold; }
    .time-badge { font-size: 1.1rem; margin-right: 15px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

def limpiar_id(t):
    if pd.isna(t): return ""
    return "".join(filter(str.isalnum, str(t))).upper()

# ─── CARGA DE DATOS ──────────────────────────────────────────────────────────
@st.cache_data(ttl=10)
def cargar_datos():
    # 1. RESERVAS (GOOGLE SHEETS)
    url_res = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"
    df_reservas = pd.DataFrame()
    try:
        res_raw = requests.get(url_res).text.splitlines()
        start_row = 0
        for i, line in enumerate(res_raw):
            if "Marca temporal" in line: start_row = i; break
        df_tmp = pd.read_csv(io.StringIO("\n".join(res_raw[start_row:])))
        df_reservas['actividad'] = df_tmp.iloc[:, 4]
        df_reservas['fecha'] = pd.to_datetime(df_tmp.iloc[:, 6], dayfirst=True, errors='coerce').dt.date
        df_reservas['aula_id'] = df_tmp.iloc[:, 7].apply(limpiar_id)
        df_reservas['h_ini'] = df_tmp.iloc[:, 8].astype(str)
        df_reservas['h_fin'] = df_tmp.iloc[:, 9].astype(str)
        df_reservas['nombre'] = df_tmp.iloc[:, 3]
    except: pass

    # 2. HORARIO (GITHUB)
    url_hor = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"
    df_horario = pd.DataFrame()
    lista_aulas = []
    try:
        resp = requests.get(url_hor)
        df_xl = pd.read_excel(io.BytesIO(resp.content))
        df_xl["Dia"] = df_xl["Dia"].ffill()
        df_xl["Hora"] = df_xl["Hora"].ffill()
        lista_aulas = [c for c in df_xl.columns if c not in ["Dia", "Hora"]]
        
        lista_final = []
        for _, row in df_xl.iterrows():
            try:
                h_range = str(row["Hora"]).replace("–", "-").split("-")
                h_ini = datetime.strptime(h_range[0].strip(), "%H:%M").time()
                h_fin = datetime.strptime(h_range[1].strip(), "%H:%M").time()
                for aula in lista_aulas:
                    val = row[aula]
                    ocupado = not (pd.isna(val) or str(val).strip() == "")
                    lista_final.append({
                        "Dia": str(row["Dia"]).strip(),
                        "HoraStr": str(row["Hora"]),
                        "H_Ini": h_ini, "H_Fin": h_fin,
                        "AulaID": limpiar_id(aula),
                        "Detalle": str(val).strip() if ocupado else "Libre",
                        "Ocupado": ocupado
                    })
            except: continue
        df_horario = pd.DataFrame(lista_final)
    except: pass
    return df_reservas, df_horario, lista_aulas

df_r, df_h, lista_aulas = cargar_datos()

# ─── INTERFAZ ────────────────────────────────────────────────────────────────
st.title("🏫 Control de Aulas UPES")

if lista_aulas:
    c1, c2 = st.columns(2)
    aula_sel = c1.selectbox("Seleccione la Instalación", lista_aulas)
    fecha_sel = c2.date_input("Fecha de consulta", value=date.today())

    # Lógica de días flexible (busca "Lunes" dentro de "1.Lunes")
    nombres_dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    dia_buscado = nombres_dias[fecha_sel.weekday()]
    id_aula = limpiar_id(aula_sel)

    # Filtrar bloques del horario base
    if not df_h.empty:
        bloques = df_h[(df_h["AulaID"] == id_aula) & (df_h["Dia"].str.contains(dia_buscado, case=False, na=False))]
        
        st.subheader(f"Disponibilidad: {aula_sel} — {fecha_sel.strftime('%d/%m/%Y')}")

        if bloques.empty:
            st.warning(f"No hay bloques de clase definidos para el día {dia_buscado} en el horario base.")
            # Si no hay bloques de clase, buscamos si al menos hay reservas para ese día
            res_hoy = df_r[(df_r['fecha'] == fecha_sel) & (df_r['aula_id'] == id_aula)]
            if not res_hoy.empty:
                st.info("Sin embargo, se encontraron las siguientes reservas individuales:")
                for _, r in res_hoy.iterrows():
                    st.markdown(f'<div class="bloque reserva"><span class="time-badge">🟡 {r["h_ini"]} - {r["h_fin"]}</span> RESERVA: {r["actividad"]} ({r["nombre"]})</div>', unsafe_allow_html=True)
        else:
            for _, row in bloques.iterrows():
                tipo, detalle, icono = ("clase", row["Detalle"], "🔴") if row["Ocupado"] else ("libre", "Libre", "✅")
                
                # Cruce con reservas
                match = df_r[(df_r['fecha'] == fecha_sel) & (df_r['aula_id'] == id_aula)]
                for _, res in match.iterrows():
                    try:
                        r_ini = datetime.strptime(":".join(res['h_ini'].split(":")[:2]), "%H:%M").time()
                        r_fin = datetime.strptime(":".join(res['h_fin'].split(":")[:2]), "%H:%M").time()
                        if row["H_Ini"] < r_fin and r_ini < row["H_Fin"]:
                            tipo, detalle, icono = "reserva", f"RESERVA: {res['actividad']} ({res['nombre']})", "🟡"
                            break
                    except: continue
                
                st.markdown(f'<div class="bloque {tipo}"><span class="time-badge">{icono} {row["HoraStr"]}</span> {detalle}</div>', unsafe_allow_html=True)
