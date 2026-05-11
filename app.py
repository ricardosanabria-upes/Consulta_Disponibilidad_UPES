"""
Consulta de Disponibilidad de Instalaciones — UPES
- Lee el Excel de horario de clases desde GitHub (se reemplaza cada ciclo)
- Lee reservas existentes desde Google Sheets en tiempo real
- Muestra disponibilidad por instalación y fecha
- Vista por día y vista semanal
"""

import streamlit as st
import pandas as pd
import io
from datetime import datetime, date, time, timedelta

st.set_page_config(
    page_title="Disponibilidad de Instalaciones — UPES",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }

    .titulo  { font-size: 2rem; font-weight: 700; color: #1e1b4b; margin-bottom: 0; }
    .sub     { color: #64748b; font-size: 0.95rem; margin-bottom: 1rem; }
    .badge   { display:inline-block; background:#ede9fe; color:#4c1d95;
               border-radius:999px; padding:2px 14px; font-size:0.78rem;
               font-weight:600; margin-bottom:1rem; }
    .libre   { background:#f0fdf4; border:1px solid #86efac; border-radius:10px;
               padding:10px 14px; margin:4px 0; font-size:0.88rem; color:#166534; }
    .clase   { background:#fef2f2; border:1px solid #fca5a5; border-radius:10px;
               padding:10px 14px; margin:4px 0; font-size:0.88rem; color:#991b1b; }
    .reserva { background:#fefce8; border:1px solid #fde047; border-radius:10px;
               padding:10px 14px; margin:4px 0; font-size:0.88rem; color:#713f12; }
    .leyenda { display:flex; gap:1.5rem; margin:1rem 0; flex-wrap:wrap; }
    .leg-item{ display:flex; align-items:center; gap:6px; font-size:0.82rem; }
    .dot-v   { width:12px; height:12px; border-radius:50%; background:#86efac; }
    .dot-c   { width:12px; height:12px; border-radius:50%; background:#fca5a5; }
    .dot-r   { width:12px; height:12px; border-radius:50%; background:#fde047; }
    /* Tabla pivot */
    .pivot-libre  { background:#f0fdf4 !important; color:#166534 !important; font-size:0.75rem; }
    .pivot-clase  { background:#fef2f2 !important; color:#991b1b !important; font-size:0.75rem; }
    .pivot-reserva{ background:#fefce8 !important; color:#713f12 !important; font-size:0.75rem; }
</style>
""", unsafe_allow_html=True)

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRTXl1SeHi0aSgyVMnLRw-f42SR9G_JEywRfvTak6nx1vyU5PQ4EnA161DheHsjjrjmjR-lJHaXzwMK/pub?gid=1879457457&single=true&output=csv"

EXCEL_GITHUB_URL = "https://raw.githubusercontent.com/ricardosanabria-upes/Reservas_UPES/main/DETALLE%20AULAS%20CICLO%20ACTUAL.xlsx"

INSTALACIONES = [
    "A-11", "A-12", "A-13", "A-14", "A-15", "A-16",
    "A-21 C/Acondicionado", "A-22 C/Acondicionado",
    "A-31", "A-32", "A-33", "A-34 (Mesas de dibujo)", "A-35", "A-36",
    "A-41", "A-42", "A-43", "A-44", "A-45", "A-46",
    "SUM", "Sala de juntas", "Pasillos", "Biblioteca",
]

DIA_SEMANA = {
    0: "1.Lunes", 1: "2.Martes", 2: "3.Miercoles",
    3: "4.Jueves", 4: "5.Viernes", 5: "6.Sabado", 6: "7.Domingo",
}
DIA_NOMBRE = {
    0: "Lunes", 1: "Martes", 2: "Miércoles",
    3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo",
}


# ─── FUNCIONES ────────────────────────────────────────────────────────────────

def normalizar_aula(aula: str) -> str:
    mapeo = {
        "A-21": "A-21 C/Acondicionado",
        "A-22": "A-22 C/Acondicionado",
        "A-34": "A-34 (Mesas de dibujo)",
    }
    return mapeo.get(aula.strip(), aula.strip())


@st.cache_data(ttl=300)  # Refresca cada 5 minutos
def cargar_reservas_sheets() -> pd.DataFrame | None:
    """Lee la hoja de Google Sheets en tiempo real."""
    try:
        df = pd.read_csv(GOOGLE_SHEET_URL, header=1)
        df.columns = df.columns.str.strip()
        rename = {}
        for col in df.columns:
            cl = col.lower().strip()
            if "instalación solicitada" in cl or "instalacion solicitada" in cl:
                rename[col] = "instalacion"
            elif "fecha del evento" in cl:
                rename[col] = "fecha"
            elif "hora de inicio" in cl:
                rename[col] = "hora_inicio"
            elif "hora de finalización" in cl or "finalización exacta" in cl:
                rename[col] = "hora_fin"
            elif "nombre completo del solicitante" in cl:
                rename[col] = "nombre"
            elif "nombre y descripción" in cl or "nombre y descripcion" in cl:
                rename[col] = "actividad"
        df = df.rename(columns=rename)
        return df
    except Exception as e:
        return None


@st.cache_data(ttl=3600)  # Refresca cada hora
def cargar_horario_github() -> pd.DataFrame | None:
    """Lee el Excel de clases desde GitHub."""
    try:
        import requests
        resp = requests.get(EXCEL_GITHUB_URL)
        resp.raise_for_status()
        df_raw = pd.read_excel(io.BytesIO(resp.content))
        df_raw.columns = df_raw.columns.str.strip()
        df_raw["Dia"]  = df_raw["Dia"].ffill()
        df_raw["Hora"] = df_raw["Hora"].ffill()

        aulas = [c for c in df_raw.columns if c not in ["Dia", "Hora"]]
        filas = []
        for _, row in df_raw.iterrows():
            dia  = str(row["Dia"]).strip()
            hora = str(row["Hora"]).strip()
            if not dia or dia == "nan" or not hora or hora == "nan":
                continue
            try:
                partes_h = hora.replace("–", "-").split("-")
                h_ini = datetime.strptime(partes_h[0].strip(), "%H:%M").time()
                h_fin = datetime.strptime(partes_h[1].strip(), "%H:%M").time()
            except Exception:
                h_ini = h_fin = None

            for aula in aulas:
                val = row[aula]
                ocupada = not (pd.isna(val) or str(val).strip() == "")
                if ocupada:
                    texto  = str(val).strip()
                    partes = texto.split()
                    codigo  = partes[0] if partes else ""
                    seccion = partes[-1] if len(partes) > 1 and partes[-1].isdigit() else ""
                    nombre  = " ".join(partes[1:-1]) if seccion else " ".join(partes[1:])
                else:
                    codigo = seccion = nombre = ""

                filas.append({
                    "Dia": dia, "Hora": hora,
                    "HoraInicio": h_ini, "HoraFin": h_fin,
                    "Aula": normalizar_aula(aula),
                    "Materia": nombre, "Codigo": codigo, "Seccion": seccion,
                    "Ocupada": ocupada
                })
        return pd.DataFrame(filas)
    except Exception as e:
        return None


def hay_traslape(ini1: time, fin1: time, ini2: time, fin2: time) -> bool:
    return ini1 < fin2 and ini2 < fin1


def get_estado_bloque(instalacion, dia_semana, hora_ini, hora_fin,
                       df_horario, df_reservas, fecha=None):
    """
    Retorna: ('libre'|'clase'|'reserva', detalle_str)
    fecha: date — filtra reservas por fecha exacta (obligatorio para validar correctamente)
    """
    # Verificar clase del ciclo
    if df_horario is not None:
        df_inst = df_horario[
            (df_horario["Aula"] == instalacion) &
            (df_horario["Dia"] == dia_semana) &
            (df_horario["Ocupada"] == True)
        ].dropna(subset=["HoraInicio", "HoraFin"])
        for _, row in df_inst.iterrows():
            if hay_traslape(hora_ini, hora_fin, row["HoraInicio"], row["HoraFin"]):
                return "clase", f"{row['Codigo']} {row['Materia']} — Sección {row['Seccion']}"

    # Verificar reserva existente — SIEMPRE filtra por fecha exacta
    if df_reservas is not None and fecha is not None:
        c_inst  = next((c for c in df_reservas.columns if c == "instalacion"), None)
        c_fecha = next((c for c in df_reservas.columns if c == "fecha"), None)
        c_ini   = next((c for c in df_reservas.columns if c == "hora_inicio"), None)
        c_fin   = next((c for c in df_reservas.columns if c == "hora_fin"), None)
        c_nom   = next((c for c in df_reservas.columns if c == "nombre"), None)
        c_act   = next((c for c in df_reservas.columns if c == "actividad"), None)

        if c_inst and c_fecha and c_ini and c_fin:
            for _, row in df_reservas.iterrows():
                if str(row[c_inst]).strip() != instalacion:
                    continue
                # Validar fecha exacta
                try:
                    fecha_r = pd.to_datetime(str(row[c_fecha]), dayfirst=True).date()
                except Exception:
                    continue
                if fecha_r != fecha:
                    continue
                try:
                    ini_r = datetime.strptime(str(row[c_ini]).strip()[:5], "%H:%M").time()
                    fin_r = datetime.strptime(str(row[c_fin]).strip()[:5], "%H:%M").time()
                except Exception:
                    continue
                if hay_traslape(hora_ini, hora_fin, ini_r, fin_r):
                    nom = str(row[c_nom]) if c_nom else "—"
                    act = str(row[c_act]) if c_act else ""
                    detalle = f"{nom}" + (f" — {act}" if act and act != "nan" else "")
                    return "reserva", detalle

    return "libre", "Disponible"


def get_bloques_dia(instalacion, fecha, df_horario, df_reservas):
    """
    Retorna lista de bloques del horario del ciclo para esa instalación/día,
    más las reservas que no coincidan con bloques del ciclo.
    """
    dia_semana = DIA_SEMANA.get(fecha.weekday(), "")
    bloques = []

    # Bloques del ciclo
    if df_horario is not None:
        df_inst = df_horario[
            (df_horario["Aula"] == instalacion) &
            (df_horario["Dia"] == dia_semana)
        ].sort_values("HoraInicio")

        for _, row in df_inst.iterrows():
            if row["Ocupada"]:
                bloques.append({
                    "hora": row["Hora"],
                    "tipo": "clase",
                    "detalle": f"{row['Codigo']} {row['Materia']} — Sección {row['Seccion']}",
                    "h_ini": row["HoraInicio"],
                    "h_fin": row["HoraFin"],
                })
            else:
                # Verificar si hay reserva en este bloque libre
                estado, detalle = get_estado_bloque(
                    instalacion, dia_semana,
                    row["HoraInicio"], row["HoraFin"],
                    None, df_reservas, fecha
                )
                if estado == "reserva":
                    bloques.append({
                        "hora": row["Hora"],
                        "tipo": "reserva",
                        "detalle": detalle,
                        "h_ini": row["HoraInicio"],
                        "h_fin": row["HoraFin"],
                    })
                else:
                    bloques.append({
                        "hora": row["Hora"],
                        "tipo": "libre",
                        "detalle": "Disponible",
                        "h_ini": row["HoraInicio"],
                        "h_fin": row["HoraFin"],
                    })

    # Reservas fuera de bloques del ciclo
    if df_reservas is not None:
        c_inst  = next((c for c in df_reservas.columns if c == "instalacion"), None)
        c_fecha = next((c for c in df_reservas.columns if c == "fecha"), None)
        c_ini   = next((c for c in df_reservas.columns if c == "hora_inicio"), None)
        c_fin   = next((c for c in df_reservas.columns if c == "hora_fin"), None)
        c_nom   = next((c for c in df_reservas.columns if c == "nombre"), None)
        c_act   = next((c for c in df_reservas.columns if c == "actividad"), None)

        if c_inst and c_fecha and c_ini and c_fin:
            for _, row in df_reservas.iterrows():
                if str(row[c_inst]).strip() != instalacion:
                    continue
                try:
                    fecha_r = pd.to_datetime(str(row[c_fecha]), dayfirst=True).date()
                except Exception:
                    continue
                if fecha_r != fecha:
                    continue
                try:
                    ini_r = datetime.strptime(str(row[c_ini]).strip()[:5], "%H:%M").time()
                    fin_r = datetime.strptime(str(row[c_fin]).strip()[:5], "%H:%M").time()
                except Exception:
                    continue

                # Solo agregar si no está ya cubierta por un bloque del ciclo
                ya_cubierta = any(
                    b["h_ini"] is not None and
                    hay_traslape(ini_r, fin_r, b["h_ini"], b["h_fin"])
                    for b in bloques
                )
                if not ya_cubierta:
                    nom = str(row[c_nom]) if c_nom else "—"
                    act = str(row[c_act]) if c_act else ""
                    detalle = nom + (f" — {act}" if act and act != "nan" else "")
                    bloques.append({
                        "hora": f"{ini_r.strftime('%H:%M')}-{fin_r.strftime('%H:%M')}",
                        "tipo": "reserva",
                        "detalle": detalle,
                        "h_ini": ini_r,
                        "h_fin": fin_r,
                    })

    bloques.sort(key=lambda b: b["h_ini"] or time(0, 0))
    return bloques


# ─── CARGAR DATOS ─────────────────────────────────────────────────────────────
df_horario  = cargar_horario_github()
df_reservas = cargar_reservas_sheets()

# Sidebar con estado de conexión
with st.sidebar:
    st.markdown("## 📡 Estado de conexión")
    st.markdown("---")

    if df_horario is not None:
        aulas_excel = sorted(df_horario["Aula"].unique().tolist())
        st.success(f"✅ Horario del ciclo cargado\n\n{len(aulas_excel)} aulas disponibles")
    else:
        aulas_excel = []
        st.error("❌ No se pudo cargar el horario del ciclo desde GitHub")

    st.markdown("")

    if df_reservas is not None:
        st.success(f"✅ Reservas en tiempo real\n\n{len(df_reservas)} registros cargados")
        if st.button("🔄 Actualizar reservas"):
            st.cache_data.clear()
            st.rerun()
    else:
        st.warning("⚠️ No se pudieron cargar las reservas de Google Sheets")

    st.markdown("---")
    st.markdown(
        "<small style='color:#94a3b8'>"
        "📊 Horario: se actualiza cada ciclo en GitHub<br><br>"
        "📋 Reservas: se actualizan automáticamente cada 5 minutos desde Google Sheets"
        "</small>", unsafe_allow_html=True
    )


# ─── HEADER ──────────────────────────────────────────────────────────────────
cl, ch = st.columns([1, 9])
with cl:
    st.markdown("<div style='font-size:2.8rem;padding-top:0.3rem'>🏫</div>", unsafe_allow_html=True)
with ch:
    st.markdown("<h1 class='titulo'>Disponibilidad de Instalaciones</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub'>Consulta en tiempo real la disponibilidad de aulas y espacios.</p>", unsafe_allow_html=True)

# Leyenda
st.markdown("""
<div class='leyenda'>
    <div class='leg-item'><div class='dot-v'></div> Libre</div>
    <div class='leg-item'><div class='dot-c'></div> Clase del ciclo</div>
    <div class='leg-item'><div class='dot-r'></div> Reservado por evento</div>
</div>
""", unsafe_allow_html=True)
st.markdown("---")

tab_dia, tab_semana = st.tabs(["📅 Consulta por fecha", "📊 Vista semanal"])


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 1 – CONSULTA POR FECHA
# ═══════════════════════════════════════════════════════════════════════════════
with tab_dia:
    c1, c2 = st.columns(2)
    with c1:
        instalacion = st.selectbox("🏛 Instalación", INSTALACIONES)
    with c2:
        fecha = st.date_input("📅 Fecha", value=date.today(), min_value=date.today() - timedelta(days=30))

    dia_nombre = DIA_NOMBRE.get(fecha.weekday(), "")
    st.markdown(f"### {instalacion} — {dia_nombre} {fecha.strftime('%d/%m/%Y')}")

    bloques = get_bloques_dia(instalacion, fecha, df_horario, df_reservas)

    if not bloques:
        st.info("No hay bloques de horario registrados para esta instalación en este día.")
    else:
        libres  = sum(1 for b in bloques if b["tipo"] == "libre")
        clases  = sum(1 for b in bloques if b["tipo"] == "clase")
        reservas = sum(1 for b in bloques if b["tipo"] == "reserva")

        m1, m2, m3 = st.columns(3)
        m1.metric("✅ Libres", libres)
        m2.metric("🔴 Clases", clases)
        m3.metric("🟡 Reservados", reservas)

        st.markdown("")
        for b in bloques:
            if b["tipo"] == "libre":
                st.markdown(
                    f"<div class='libre'>✅ <b>{b['hora']}</b> — Disponible</div>",
                    unsafe_allow_html=True
                )
            elif b["tipo"] == "clase":
                st.markdown(
                    f"<div class='clase'>🔴 <b>{b['hora']}</b> — {b['detalle']}</div>",
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f"<div class='reserva'>🟡 <b>{b['hora']}</b> — {b['detalle']}</div>",
                    unsafe_allow_html=True
                )


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 2 – VISTA SEMANAL
# ═══════════════════════════════════════════════════════════════════════════════
with tab_semana:
    inst_s = st.selectbox("🏛 Instalación", INSTALACIONES, key="inst_s")

    # Semana actual
    hoy = date.today()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    dias_semana = [inicio_semana + timedelta(days=i) for i in range(6)]  # Lun-Sab

    st.markdown(f"### {inst_s} — Semana del {inicio_semana.strftime('%d/%m')} al {(inicio_semana + timedelta(days=5)).strftime('%d/%m/%Y')}")

    # Obtener todos los bloques horarios únicos del Excel
    if df_horario is not None:
        df_inst_h = df_horario[df_horario["Aula"] == inst_s].copy()
        horas_unicas = df_inst_h[["Hora", "HoraInicio", "HoraFin"]].drop_duplicates().sort_values("HoraInicio")
    else:
        horas_unicas = pd.DataFrame(columns=["Hora", "HoraInicio", "HoraFin"])

    if horas_unicas.empty:
        st.info("Sube el Excel del horario para ver la vista semanal.")
    else:
        # Construir tabla
        tabla = []
        for _, hora_row in horas_unicas.iterrows():
            fila = {"Hora": hora_row["Hora"]}
            for dia_fecha in dias_semana:
                dia_semana_key = DIA_SEMANA.get(dia_fecha.weekday(), "")
                dia_nom = DIA_NOMBRE.get(dia_fecha.weekday(), "")
                col_key = f"{dia_nom}\n{dia_fecha.strftime('%d/%m')}"

                if hora_row["HoraInicio"] is None or hora_row["HoraFin"] is None:
                    fila[col_key] = "—"
                    continue

                estado, detalle = get_estado_bloque(
                    inst_s, dia_semana_key,
                    hora_row["HoraInicio"], hora_row["HoraFin"],
                    df_horario, df_reservas, dia_fecha
                )

                # Para la vista semanal ya no necesitamos segunda llamada
                # get_estado_bloque ya filtra por fecha correctamente

                if estado == "libre":
                    fila[col_key] = "✅ Libre"
                elif estado == "clase":
                    mat = detalle.split("—")[0].strip() if "—" in detalle else detalle
                    fila[col_key] = f"🔴 {mat[:25]}"
                else:
                    nom = detalle.split("—")[0].strip() if "—" in detalle else detalle
                    fila[col_key] = f"🟡 {nom[:25]}"

            tabla.append(fila)

        df_tabla = pd.DataFrame(tabla).set_index("Hora")

        def color_celda(val):
            if str(val).startswith("✅"):
                return "background-color: #f0fdf4; color: #166534;"
            elif str(val).startswith("🔴"):
                return "background-color: #fef2f2; color: #991b1b;"
            elif str(val).startswith("🟡"):
                return "background-color: #fefce8; color: #713f12;"
            return ""

        st.dataframe(
            df_tabla.style.map(color_celda),
            use_container_width=True,
            height=380
        )

        # Resumen de la semana
        st.markdown("---")
        total_bloques = df_tabla.size
        libres_s  = df_tabla.apply(lambda col: col.str.startswith("✅")).sum().sum()
        clases_s  = df_tabla.apply(lambda col: col.str.startswith("🔴")).sum().sum()
        reservas_s = df_tabla.apply(lambda col: col.str.startswith("🟡")).sum().sum()
        pct = round(libres_s / total_bloques * 100) if total_bloques else 0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total bloques", total_bloques)
        m2.metric("✅ Libres", libres_s)
        m3.metric("🔴 Clases", clases_s)
        m4.metric("🟡 Reservados", reservas_s)

