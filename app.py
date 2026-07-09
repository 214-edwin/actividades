import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_calendar import calendar
from datetime import datetime
import os
import uuid
import time
from io import BytesIO
import gspread
from supabase import create_client
from google.oauth2.service_account import Credentials
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)
#####################################################
def subir_pdf(file, nombre, usuario):
    file_id = str(uuid.uuid4())

    # 🔴 LIMPIEZA CRÍTICA
    safe_user = usuario.replace(" ", "_")

    path = f"vacaciones/{safe_user}/{file_id}_{nombre}"

    file_bytes = file.getvalue()

    supabase.storage.from_("vacaciones-pdfs").upload(
        path,
        file_bytes,
        file_options={"content-type": "application/pdf"}
    )

   
    url = supabase.storage.from_("vacaciones-pdfs").create_signed_url(
        path,
        60 * 60 * 24 * 365
    )["signedURL"]

    return url
##################################
 
######################################

st.set_page_config(page_title="Sistema de Vacaciones", layout="wide")

######################################################################
tab1, tab2, tab3 = st.tabs([
    "Calendario",
    "Actividades semanales",
    "Seguimiento"
])
####################espacio inicial ###################################
st.markdown("""
<style>

/* QUITA ESPACIO SUPERIOR DE LA APP */
.block-container {
    padding-top: 0.5rem !important;
}

/* opcional: reduce aún más el espacio del header */
header {
    visibility: hidden;
    height: 0px;
}

</style>
""", unsafe_allow_html=True)
###################color cabezasde titulos ##############
st.markdown("""
<style>

/* EXPANDER HEADER (Nuevo registro) */
div[data-testid="stExpander"] summary {
    background-color: #0d4985 !important;
    color: white !important;
    padding: 0.6rem;
    border-radius: 8px;
    font-weight: bold;
}

/* HOVER */
div[data-testid="stExpander"] summary:hover {
    background-color: #1565c0 !important;
}

</style>
""", unsafe_allow_html=True)


with tab1:
# --------------------------
# HEADER
# --------------------------
    col1, col2 = st.columns([5,1])

    with col1:
        st.title("Calendario de Actividades")
    with col2:
        st.image("www/logosunass.png", width=100)

    # -----------------------
    # PATHS
    # -----------------------
    @st.cache_data(ttl=300)
    def cargar_trabajadores():

        response = (
            supabase
            .table("trabajadores")
            .select("*")
            .execute()
        )

        return pd.DataFrame(response.data)

    trabajadores = cargar_trabajadores()

    #  CARGAR DATOS DESDE GOOGLE SHEETS
    @st.cache_data(ttl=300)
    def cargar_registros():
        response = (
            supabase
            .table("vacaciones")
            .select("*")
            .execute()
        )

        return pd.DataFrame(response.data)

    if "registros" not in st.session_state:
        st.session_state.registros = cargar_registros()

    registros = st.session_state.registros
    
    if "id" in registros.columns and not registros.empty:
        if st.session_state.get("edit_id") is not None:
            if str(st.session_state.edit_id) not in registros["id"].astype(str).values:
                st.session_state.edit_id = None
    registros["fecha_inicio"] = pd.to_datetime(registros["fecha_inicio"], format="mixed", errors="coerce")
    registros["fecha_fin"] = pd.to_datetime(registros["fecha_fin"], format="mixed", errors="coerce")
    if st.session_state.get("guardado_ok"):
        st.success("✅ Guardado exitosamente")
        st.session_state["guardado_ok"] = False
    if st.session_state.get("eliminado_ok"):
        st.success("✅ Registro eliminado correctamente")
        st.session_state["eliminado_ok"] = False
    # 🧠 si está vacío, crear estructura
    if registros.empty:
        registros = pd.DataFrame(columns=[
            "id","trabajador","sede","tipo",
            "fecha_inicio","fecha_fin",
            "observacion","archivo",
            "fecha_registro","estado"
        ])

    # 🔧 limpieza de seguridad
    registros["observacion"] = registros["observacion"].astype(str)
    registros["archivo"] = registros["archivo"].astype(str)

    registros = registros[registros["estado"] == "activo"]

    lista_trabajadores = trabajadores["Apellidos y nombre"].tolist()
    mapa_sede = dict(zip(trabajadores["Apellidos y nombre"], trabajadores["Sede"]))

    # -----------------------
    # SESSION STATE
    # -----------------------
    if "edit_id" not in st.session_state:
        st.session_state.edit_id = None

    # -----------------------
    # REGISTRO EDIT
    # -----------------------
    registro_edit = None

    edit_id = st.session_state.get("edit_id", None)

    if edit_id is not None:
        tmp = registros[registros["id"] == edit_id]
        if not tmp.empty:
            registro_edit = tmp.iloc[0]

    # -----------------------
    # FUNCIONES
    # -----------------------
    def hay_solapamiento(df, trabajador, inicio, fin, edit_id=None):
        df = df[df["trabajador"] == trabajador]

        if df.empty:
            return False

        inicio = pd.to_datetime(inicio)
        fin = pd.to_datetime(fin)

        for _, row in df.iterrows():

            # ❗ ignorar el mismo registro cuando estás editando
            if edit_id is not None and row["id"] == edit_id:
                continue

            ini = pd.to_datetime(row["fecha_inicio"])
            fin_r = pd.to_datetime(row["fecha_fin"])

            if not (fin < ini or inicio > fin_r):
                return True

        return False
    
    # -----------------------
    # FORMULARIO
    # -----------------------
    titulo_form = "✏️ Editando registro" if st.session_state.edit_id is not None else "➕ Nuevo registro"
    st.markdown("<div id='top_form'></div>", unsafe_allow_html=True)
    if st.session_state.edit_id is not None:
        st.markdown("""
        <script>
        setTimeout(() => {
            document.querySelector('#top_form')?.scrollIntoView();
        }, 300);
        </script>
        """, unsafe_allow_html=True)

    with st.expander(
        titulo_form,
        expanded=st.session_state.edit_id is not None
    ):
        with st.form("form", clear_on_submit=True):

            opciones_trabajador = ["Seleccionar..."] + lista_trabajadores

            default_trabajador = registro_edit["trabajador"] if registro_edit is not None else "Seleccionar..."
            default_tipo = registro_edit["tipo"] if registro_edit is not None else "Vacaciones"

            trabajador = st.selectbox(
                "Trabajador",
                opciones_trabajador,
                index=opciones_trabajador.index(default_trabajador)
            )

            tipo = st.selectbox(
                "Tipo",
                ["Vacaciones", "Comisión", "Otro"],
                index=["Vacaciones", "Comisión", "Otro"].index(default_tipo)
            )
            
            

            col1, col2 = st.columns(2)

            if registro_edit is not None:
                inicio_default = pd.to_datetime(registro_edit["fecha_inicio"]).date()
                fin_default = pd.to_datetime(registro_edit["fecha_fin"]).date()
            else:
                inicio_default = datetime.today().date()
                fin_default = datetime.today().date()
            with col1:
                inicio = st.date_input("Fecha inicio", value=inicio_default)

            with col2:
                fin = st.date_input("Fecha fin", value=fin_default)

            
            ###############
            # ---------------- OBSERVACIÓN ----------------
            observacion = st.text_area(
                "Observación (ser breve, 1 a 2 palabras o frase corta)\nEjemplos:",
                value=registro_edit["observacion"] if registro_edit is not None else "",
                placeholder="""Si es comisión llenar lugar y actividad: Apurimac:Grau - cuota / ADP
                Si es Otro: cumpleaños / salud
                Si es vacaciones: Dejar vacío""")
            ########################
            archivo = st.file_uploader("Archivo (Subir plan de trabajo en caso de comisión)")

            col_a, col_b = st.columns(2)

            with col_a:
                enviar = st.form_submit_button("Guardar")
                if enviar:
                    st.info("⏳ Guardando...")
            with col_b:
                limpiar = st.form_submit_button("Limpiar")
            if st.session_state.edit_id is not None:

                cancelar = st.form_submit_button("Cancelar edición")

                if cancelar:
                    st.session_state.edit_id = None
                    st.rerun()

    # -----------------------
    # GUARDADO
    # -----------------------
    if "lock_guardar" not in st.session_state:
       st.session_state.lock_guardar = False
    
    if enviar:
        if st.session_state.lock_guardar:
            st.stop()

        st.session_state.lock_guardar = True
        try:

            if trabajador == "Seleccionar...":
                st.warning("Selecciona un trabajador")
                st.stop()

            if inicio > fin:
                st.error("La fecha de inicio no puede ser mayor que la fecha fin. Volver a registrar")
                st.stop()

            df_validacion = registros.copy()

            if st.session_state.edit_id is not None:
                df_validacion = df_validacion[df_validacion["id"] != st.session_state.edit_id]

            if hay_solapamiento(df_validacion, trabajador, inicio, fin):
                st.error("❌ Ya existe un registro en esas fechas para este trabajador")
                st.stop()

            if archivo:
                st.write("Subiendo PDF...")
                ruta_archivo = subir_pdf(archivo, archivo.name, trabajador)
                st.write("PDF listo")
            else:
                ruta_archivo = ""

            if st.session_state.edit_id is None:
                nuevo_id = str(uuid.uuid4())
            else:
                nuevo_id = st.session_state.edit_id

            nueva_fila = {
                "id": nuevo_id,
                "trabajador": trabajador,
                "sede": mapa_sede[trabajador],
                "tipo": tipo,
                "fecha_inicio": str(inicio),
                "fecha_fin": str(fin),
                "observacion": observacion,
                "archivo": ruta_archivo,
                "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "estado": "activo"
            }

            if st.session_state.edit_id is None:
            # 🆕 CREAR
                response = (
                    supabase
                    .table("vacaciones")
                    .insert(nueva_fila)
                    .execute()
                )

                registros = pd.concat(
                    [registros, pd.DataFrame([nueva_fila])],
                    ignore_index=True
                )
            else:
                # ✏️ EDITAR (actualización limpia)
                idx = registros.index[registros["id"] == st.session_state.edit_id]

                if len(idx) > 0:
                    registros.loc[idx, "trabajador"] = nueva_fila["trabajador"]
                    registros.loc[idx, "sede"] = nueva_fila["sede"]
                    registros.loc[idx, "tipo"] = nueva_fila["tipo"]
                    registros.loc[idx, "fecha_inicio"] = nueva_fila["fecha_inicio"]
                    registros.loc[idx, "fecha_fin"] = nueva_fila["fecha_fin"]
                    registros.loc[idx, "observacion"] = nueva_fila["observacion"]
                    registros.loc[idx, "archivo"] = nueva_fila["archivo"]
                    registros.loc[idx, "fecha_registro"] = nueva_fila["fecha_registro"]
                    registros.loc[idx, "estado"] = nueva_fila["estado"]

            st.cache_data.clear()
            st.session_state.edit_id = None
            st.session_state.lock_guardar = False
            st.session_state["guardado_ok"] = True
            st.rerun()
        except Exception as e:
            st.session_state["error"] = str(e)
            st.error(f"ERROR: {e}")
            st.stop()    
    if limpiar:
        st.session_state.edit_id = None
        st.rerun()    


    # -----------------------
    # LAYOUT PRINCIPAL
    # -----------------------
    col_izq, col_der = st.columns([1,2])

    with col_izq:

        # FILTROS
        seleccionados = st.multiselect("Selecciona trabajadores", lista_trabajadores)

        meses = {
            "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4,
            "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8,
            "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12
        }

        mes_seleccionado = st.selectbox("Mes", ["Seleccionar..."] + list(meses.keys()))

        tipos_seleccionados = st.multiselect(
            "Tipo",
            ["Vacaciones", "Comisión", "Otro"]
        )
        st.markdown("""
        ### 🧾 Leyenda

        🟢 **Vacaciones** → 🏖️☀️  
        🟠 **Comisión** → ✈️  
        🔵 **Otro** → 📄  
        """)
        # -----------------------
        # REGISTROS VISIBLES (PASO 1)
        # -----------------------
        with st.expander("📋 Registros visibles", expanded=True):
            

            if len(seleccionados) == 0:
                st.info("Selecciona un trabajador para ver sus registros")
                df_visible = pd.DataFrame(columns=registros.columns)

            else:
                df_visible = registros.copy()

                df_visible = df_visible[df_visible["trabajador"].isin(seleccionados)]
                
                if mes_seleccionado != "Seleccionar...":
                    numero_mes = meses[mes_seleccionado]

                    df_visible = df_visible[
                        (df_visible["fecha_inicio"].dt.month == numero_mes) |
                        (df_visible["fecha_fin"].dt.month == numero_mes)
                    ]

                if df_visible.empty:
                    st.warning("No hay registros para este trabajador")

            for _, row in df_visible.iterrows():

                st.markdown("---")

                col1, col2 = st.columns([4, 2])

                with col1:
                    st.write(f"**{row['trabajador']}**")
                    st.write(f"{row['tipo']}")
                    st.write(
                        f"{pd.to_datetime(row['fecha_inicio']).strftime('%Y-%m-%d')} → "
                        f"{pd.to_datetime(row['fecha_fin']).strftime('%Y-%m-%d')}"
    )
                    if pd.notna(row["observacion"]) and str(row["observacion"]).strip() not in ["", "nan"]:
                     st.caption(f"📝 {row['observacion']}")

                with col2:

                    #if st.button("✏️ Editar", key=f"edit_{row['id']}"):
                        #st.session_state.edit_id = row["id"]
                        #st.session_state.scroll = True
                        #st.rerun()

                    if st.button("🗑️ Eliminar", key=f"del_{row['id']}"):

                        st.session_state[f"confirm_delete_{row['id']}"] = True

                    if st.session_state.get(f"confirm_delete_{row['id']}", False):

                        st.warning("⚠️ ¿Estás seguro?")

                        col_yes, col_no = st.columns(2)

                        with col_yes:
                            if st.button("✅ Sí", key=f"yes_{row['id']}"):

                                registros.loc[registros["id"] == row["id"], "estado"] = "inactivo"

                                (
                                    supabase
                                    .table("vacaciones")
                                    .update({"estado": "inactivo"})
                                    .eq("id", row["id"])
                                    .execute()
                                )

                                st.cache_data.clear()
                                st.session_state["eliminado_ok"] = True
                                time.sleep(0.25)
                                st.rerun()

                        with col_no:
                            if st.button("❌ No", key=f"no_{row['id']}"):

                                st.session_state[f"confirm_delete_{row['id']}"] = False
                                st.rerun()
        
        # -----------------------
        # FILTRO REAL
        # -----------------------
        if len(seleccionados) == 0 and mes_seleccionado == "Seleccionar...":

            df = pd.DataFrame(columns=registros.columns)

        else:

            df = registros.copy()

            # FILTRO TRABAJADOR
            if len(seleccionados) > 0:
                df = df[df["trabajador"].isin(seleccionados)]

            # FILTRO TIPO
            if tipos_seleccionados:
                df = df[df["tipo"].isin(tipos_seleccionados)]

            # FILTRO MES
            if mes_seleccionado != "Seleccionar...":

                numero_mes = meses[mes_seleccionado]

                df = df[
                    (df["fecha_inicio"].dt.month == numero_mes) |
                    (df["fecha_fin"].dt.month == numero_mes)
                ]
        # DOCUMENTOS
        st.subheader("📎 Documentos")

        for _, row in df.iterrows():
            if isinstance(row["archivo"], str) and row["archivo"] != "":

                st.markdown(f"📄 **{row['trabajador']}**")

                st.markdown(f"[📎 Abrir PDF]({row['archivo']})")
    with col_der:

        st.subheader("📅 Calendario")

        # -----------------------
        # EVENTOS
        # -----------------------
        if df.empty:
            events = []
        else:
            colores = {
            "Vacaciones": "#28a745",
            "Comisión": "#fd7e14",
            "Otro": "#0d6efd"
            }

            iconos = {
                "Vacaciones": "🏖️☀️",
                "Comisión": "✈️",
                "Otro": "📄"
            }

            events = []

            for _, r in df.iterrows():

                events.append({
                    "title": (
                        f"{iconos.get(r['tipo'], '📌')} "
                        f"{trabajadores.loc[trabajadores['Apellidos y nombre'] == r['trabajador'], 'Nombre corto'].values[0]}"
                        + (
                            f"\n{str(r['observacion']).strip()}"
                            if pd.notna(r['observacion'])
                            and str(r['observacion']).strip() != ''
                            and str(r['observacion']).strip().lower() != 'nan'
                            else ''
                        )
                    ),
                    "start": pd.to_datetime(r["fecha_inicio"]).strftime("%Y-%m-%d"),
                    "end": (pd.to_datetime(r["fecha_fin"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                    "color": colores.get(r["tipo"], "#6c757d")
                })
        # -----------------------
        # FECHA INICIAL DEL CALENDARIO
        # -----------------------
        if mes_seleccionado != "Seleccionar...":

            numero_mes = meses[mes_seleccionado]

            # Año actual
            anio_actual = datetime.today().year

            # Fecha inicial del calendario
            initial_date = f"{anio_actual}-{numero_mes:02d}-01"

        else:
            initial_date = datetime.today().strftime("%Y-%m-%d")

        # -----------------------
        # CALENDARIO
        # -----------------------
        
        calendar(
        events=events,
        options={
            "initialDate": initial_date,
            "headerToolbar": {
                "left": "",
                "center": "title",
                "right": ""
            }
        },

        custom_css="""
        .fc {
            background-color: #FFFFFF;
        }

        .fc-theme-standard td,
        .fc-theme-standard th {
            background-color: #FCFCFC;
        }

        .fc-col-header-cell {
            background-color: #F5F7FA;
        }
        """
    )
    
       
# =====================================================
# SEGUNDA HOJA : ACTIVIDADES SEMANALES
# =====================================================

with tab2:
    

    @st.cache_data(ttl=300)
    def cargar_trabajadores():
        response = (
            supabase
            .table("trabajador2")
            .select("*")
            .execute()
        )

        return pd.DataFrame(response.data)
    trab_df = cargar_trabajadores()
    lista_trabajadores_semanal = (
        trab_df[trab_df["estado"] == "activo"]["trabajador"]
        .tolist()
    )
    
###
    
    # =====================================
    # LOGIN ACTIVIDADES
    # =====================================
    if "usuario_actividades" not in st.session_state:
        st.session_state.usuario_actividades = None

    if "rol_actividades" not in st.session_state:
        st.session_state.rol_actividades = None
#######################################################################
    st.title("📋 Actividades Semanales")
    if st.session_state.get("semana_guardada_ok"):
       st.success("✅ La semana fue registrada correctamente.")
    if st.session_state.usuario_actividades is None:

        st.subheader("🔐 Acceso")

        trabajador_login = st.selectbox(
            "Trabajador",
            lista_trabajadores_semanal,
            key="trabajador_login"
        )

        clave_login = st.text_input(
            "Clave",
            type="password"
        )

        if st.button("Ingresar"):

            usuario = trab_df[
                (trab_df["trabajador"] == trabajador_login)
                &
                (trab_df["clave"].astype(str) == str(clave_login))
                &
                (trab_df["estado"] == "activo")
            ]

            if usuario.empty:
                st.error("Clave incorrecta")
                st.stop()

            st.session_state.usuario_actividades = trabajador_login
            st.session_state.rol_actividades = usuario.iloc[0]["rol"]

            st.rerun()

        #st.stop()
    else:   
        st.success(
            f"Usuario conectado: {st.session_state.usuario_actividades}"
        )

        if st.button("Cerrar sesión"):
            st.session_state.usuario_actividades = None
            st.session_state.rol_actividades = None
            st.rerun()
        col_izq, col_der = st.columns([2, 1])

        # =========================
        # FORM VERSION (RESET REAL)
        # =========================
        if "form_id" not in st.session_state:
            st.session_state.form_id = 0

        # =========================
        # CARGA DATOS
        # =========================
        @st.cache_data(ttl=300)
        def cargar_actividades():
            response = (
                supabase
                .table("actividades")
                .select("*")
                .execute()
            )

            df = pd.DataFrame(response.data)

            if df.empty:
                df = pd.DataFrame(columns=[
                    "id",
                    "trabajador",
                    "fecha",
                    "actividad",
                    "estado",
                    "fecha_registro",
                    "fecha_actualizacion",
                    "semana",
                    "anio",
                    "motivo_eliminacion"
                ])

            return df

        if "actividades_df" not in st.session_state:
            st.session_state.actividades_df = cargar_actividades()

        actividades_df = cargar_actividades()
        actividades_df["fecha"] = pd.to_datetime(actividades_df["fecha"], errors="coerce")

        @st.cache_data(ttl=300)
        def cargar_observaciones():
            response = (
                supabase
                .table("observaciones")
                .select("*")
                .execute()
            )
            df = pd.DataFrame(response.data)

            if not df.empty:
                df.columns = df.columns.str.strip()

            return df
        obs_df = cargar_observaciones()

        if not obs_df.empty:
            obs_df.columns = obs_df.columns.str.strip()
            
        def obtener_observacion(trabajador, semana, anio):
            if obs_df.empty:
                return ""

            data = obs_df[
                (obs_df["trabajador"] == trabajador) &
                (obs_df["semana"].astype(int) == semana) &
                (obs_df["anio"].astype(int) == anio)
            ]

            if data.empty:
                return ""

            return data.iloc[0]["observacion"]
            

        with col_izq:
            with st.expander("📋 Registro de actividades", expanded=True):
                st.subheader("Registro de actividades")

                trabajador_act = st.session_state.usuario_actividades

                from datetime import timedelta

                st.markdown("### Seleccionar semana")

                lunes_semana = st.date_input(
                    "Lunes de la semana",
                    value=None,
                    key="lunes_semana"
                )

                dias_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

                if lunes_semana:

                    if lunes_semana.weekday() != 0:
                        st.warning("Debe seleccionar un lunes")
                        st.stop()

                    dias_semana = [
                        ("Lunes", lunes_semana),
                        ("Martes", lunes_semana + timedelta(days=1)),
                        ("Miércoles", lunes_semana + timedelta(days=2)),
                        ("Jueves", lunes_semana + timedelta(days=3)),
                        ("Viernes", lunes_semana + timedelta(days=4))
                    ]

                    actividades_semana = {}

                    for nombre_dia, fecha_dia in dias_semana:

                        st.markdown(
                            f"### {nombre_dia} ({fecha_dia.strftime('%d/%m/%Y')})"
                        )

                        key = f"{st.session_state.form_id}_{nombre_dia}_acts"

                        if key not in st.session_state:
                            st.session_state[key] = [""]

                        actividades_semana[nombre_dia] = []

                        for i in range(len(st.session_state[key])):

                            input_key = f"{st.session_state.form_id}_{lunes_semana}_{nombre_dia}_{i}"

                            st.session_state[key][i] = st.text_input(
                                f"{nombre_dia} {i+1}",
                                value=st.session_state[key][i],
                                key=f"actividad_{nombre_dia}_{i}"
                            )

                        if st.button(f"➕ Agregar actividad - {nombre_dia}"):

                            st.session_state[key].append("")
                            st.rerun()

                        for act in st.session_state[key]:
                            actividades_semana[nombre_dia].append((fecha_dia, act))

            if st.button("💾 Guardar semana"):

                filas = []

                for nombre_dia, lista_actividades in actividades_semana.items():

                    for fecha_dia, actividad in lista_actividades:

                        if str(actividad).strip():

                            filas.append([
                                str(uuid.uuid4()),
                                trabajador_act,
                                fecha_dia.strftime("%Y-%m-%d"),
                                actividad,
                                "No iniciado",
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                ""
                            ])

                if filas:
                    anio = lunes_semana.year
                    semana = lunes_semana.isocalendar()[1]

                    actividades_df["semana"] = actividades_df["fecha"].dt.isocalendar().week
                    actividades_df["anio"] = actividades_df["fecha"].dt.year

                    ya_existe = actividades_df[
                        (actividades_df["trabajador"] == trabajador_act) &
                        (actividades_df["semana"] == semana) &
                        (actividades_df["anio"] == anio)
                    ]

                    if not ya_existe.empty:
                        st.warning("⚠️ Esta semana ya tiene actividades registradas para este trabajador")
                        st.stop()

                    datos = []

                    for fila in filas:
                        datos.append({
                            "id": fila[0],
                            "trabajador": fila[1],
                            "fecha": fila[2],
                            "actividad": fila[3],
                            "estado": fila[4],
                            "fecha_registro": fila[5],
                            "fecha_actualizacion": None if fila[6] == "" else fila[6],
                            "semana": semana,
                            "anio": anio,
                            "motivo_eliminacion": ""
                        })

                    supabase.table("actividades").insert(datos).execute()
                    
                    cargar_actividades.clear()
                    st.session_state.actividades_df = cargar_actividades()
                    st.success("Semana guardada correctamente")

                    # 🔥 RESET REAL (CLAVE)
                    st.session_state.form_id += 1
                    st.rerun()

            st.divider()

            st.subheader("🔎 Consultar semana")

            trabajador_consulta = st.session_state.usuario_actividades

            st.info(
                f"Consultando actividades de: {trabajador_consulta}"
            )

            lunes_consulta = st.date_input(
                "Lunes a consultar",
                value=None,
                key="lunes_consulta"
            )

            # =========================
            # EDITAR
            # =========================
            if "edit_actividad_id" not in st.session_state:
                st.session_state.edit_actividad_id = None

            if lunes_consulta:

                semana_consulta = lunes_consulta.isocalendar()[1]
                anio_consulta = lunes_consulta.year

                actividades_df["semana"] = actividades_df["fecha"].dt.isocalendar().week
                actividades_df["anio"] = actividades_df["fecha"].dt.year

                df_semana = actividades_df[
                (actividades_df["trabajador"] == trabajador_consulta)
                &
                (actividades_df["semana"] == semana_consulta)
                &
                (actividades_df["anio"] == anio_consulta)
                ].copy()

                st.markdown(f"### Semana {semana_consulta}")
                st.markdown("""
                ### Leyenda de estados
                🔴 No iniciado  
                🟡 En proceso  
                🔵 Concluido  
                """)

                dias = [
                    ("Monday", "Lunes"),
                    ("Tuesday", "Martes"),
                    ("Wednesday", "Miércoles"),
                    ("Thursday", "Jueves"),
                    ("Friday", "Viernes")
                ]

                for dia_eng, dia_es in dias:

                    st.markdown(f"#### {dia_es}")
                    df_semana["fecha"] = pd.to_datetime(df_semana["fecha"], errors="coerce")
                    df_dia = df_semana[
                        df_semana["fecha"].dt.day_name() == dia_eng
                    ]
                    df_dia = df_dia[df_dia["estado"] != "inactivo"]
                    if df_dia.empty:
                        st.caption("Sin actividades")
                    else:
                        for _, row in df_dia.iterrows():

                            col1, col2, col3, col4 = st.columns([6, 1, 1, 1])

                            estado_color = {
                                "No iniciado": "🔴",
                                "En proceso": "🟡",
                                "Concluido": "🔵"
                            }

                            with col1:
                                st.write("•", row["actividad"])

                            with col2:
                                st.write(estado_color.get(row["estado"], "🔴"))

                            with col3:
                                if st.button("✏️", key=f"edit_{row['id']}"):
                                    st.session_state.edit_actividad_id = row["id"]
                                    st.rerun()
                            with col4:
                                if st.button("🗑️", key=f"del_{row['id']}"):
                                    st.session_state[f"confirm_delete_{row['id']}"] = True

                                if st.session_state.get(f"confirm_delete_{row['id']}", False):

                                    motivo = st.text_area(
                                        "Motivo de eliminación",
                                        key=f"motivo_{row['id']}"
                                    )

                                    col_yes, col_no = st.columns(2)

                                    with col_yes:
                                        if st.button("✅", key=f"yes_{row['id']}"):

                                            actividades_df.loc[
                                                actividades_df["id"] == row["id"],
                                                "estado"
                                            ] = "inactivo"
                                            
                                            actividades_df.loc[
                                                actividades_df["id"] == row["id"],
                                                "fecha_actualizacion"
                                            ] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                                            actividades_df.loc[
                                                actividades_df["id"] == row["id"],
                                                "motivo_eliminacion"
                                            ] = motivo

                                            supabase.table("actividades").update({
                                                "estado": "inactivo",
                                                "fecha_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                                "motivo_eliminacion": motivo
                                            }).eq("id", row["id"]).execute()

                                            st.cache_data.clear()
                                            st.rerun()

                                    with col_no:
                                        if st.button("❌", key=f"no_{row['id']}"):

                                            st.session_state[f"confirm_delete_{row['id']}"] = False
                                            st.rerun()
                                    
                            # ✏️ EDITOR (INLINE BAJO EL DÍA)

                            if st.session_state.get("edit_actividad_id") == row["id"]:

                                st.markdown("### ✏️ Editando actividad")

                                nuevo_texto = st.text_input(
                                    "Editar actividad",
                                    value=row["actividad"],
                                    key=f"edit_input_{row['id']}_{st.session_state.get('edit_actividad_id', '')}"
                                )

                                col1, col2 = st.columns(2)

                                with col1:
                                    if st.button("💾 Guardar cambio", key=f"save_{row['id']}"):

                                        actividades_df.loc[
                                            actividades_df["id"] == row["id"],
                                            "actividad"
                                        ] = nuevo_texto
                                        
                                        actividades_df.loc[
                                            actividades_df["id"] == row["id"],
                                            "fecha_actualizacion"
                                        ] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                                        actividades_df.loc[
                                            actividades_df["id"] == row["id"],
                                            "estado"
                                        ] = "No iniciado"

                                        supabase.table("actividades").update({
                                            "actividad": nuevo_texto,
                                            "fecha_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                            "estado": "No iniciado",
                                            "motivo_eliminacion": f"Editado: antes '{row['actividad']}' → ahora '{nuevo_texto}'"
                                        }).eq("id", row["id"]).execute()

                                        st.cache_data.clear()
                                        st.session_state.edit_actividad_id = None
                                        time.sleep(0.25)
                                        st.rerun()

                                with col2:
                                    if st.button("❌ Cancelar", key=f"cancel_{row['id']}"):
                                        st.session_state.edit_actividad_id = None
                                        st.rerun()

                    st.button(f"➕ Agregar actividad en {dia_es}", key=f"add_{dia_es}")

                    if st.session_state.get(f"add_{dia_es}"):

                        fecha_dia = lunes_consulta + timedelta(
                            days=["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"].index(dia_es)
                        )

                        supabase.table("actividades").insert({
                            "id": str(uuid.uuid4()),
                            "trabajador": trabajador_consulta,
                            "fecha": fecha_dia.strftime("%Y-%m-%d"),
                            "actividad": "",
                            "estado": "No iniciado",
                            "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "fecha_actualizacion": None,
                            "semana": semana_consulta,
                            "anio": anio_consulta,
                            "motivo_eliminacion": ""
                        }).execute()

                        st.cache_data.clear()
                        time.sleep(0.25)
                        st.rerun()

        # =========================
        # DERECHA (SOLO ESPACIOS)
        # =========================
        with col_der:

            st.subheader("📝 Observaciones")

            if trabajador_consulta and lunes_consulta:

                semana_consulta = lunes_consulta.isocalendar()[1]
                anio_consulta = lunes_consulta.year

                obs = obtener_observacion(
                    trabajador_consulta,
                    semana_consulta,
                    anio_consulta
                )

                if obs and str(obs).strip() != "":
                    st.text_area(
                        "Observación semanal",
                        value=obs,
                        height=150,
                        disabled=True
                    )
                else:
                    st.info("No hay observación registrada para esta semana")
            else:
                st.info("Selecciona trabajador y semana en Consultar semana")

            st.subheader("📊 Gráfico de estado")
            import plotly.express as px

            if lunes_consulta and trabajador_consulta:

                df_chart = df_semana.copy()

                if not df_chart.empty:
                    df_chart = df_chart[df_chart["estado"] != "inactivo"]
                    conteo = df_chart["estado"].value_counts().reset_index()
                    conteo.columns = ["estado", "cantidad"]

                    colores = {
                        "No iniciado": "#dc3545",
                        "En proceso": "#ffc107",
                        "Concluido": "#0d6efd"
                    }

                    fig = px.pie(
                        conteo,
                        names="estado",
                        values="cantidad",
                        hole=0.5,
                        color="estado",
                        color_discrete_map=colores
                    )

                    fig.update_traces(textinfo="percent+label")

                    fig.update_layout(
                        showlegend=True,
                        margin=dict(t=20, b=20, l=20, r=20)
                    )

                    st.plotly_chart(fig, width="stretch")

                else:
                    st.info("No hay datos para graficar")
            else:
                st.info("Selecciona trabajador y semana")
            
# =====================================================
# TERCERA HOJA : SUPERVISIÓN JEFE
# =====================================================

# =========================
# CARGAS GLOBALES (FUERA DE TAB3)
# =========================

@st.cache_data(ttl=300)
def cargar_trabajadores():
    response = (
        supabase
        .table("trabajador2")
        .select("*")
        .execute()
    )
    return pd.DataFrame(response.data)


@st.cache_data(ttl=300)
def cargar_actividades():
    response = (
        supabase
        .table("actividades")
        .select("*")
        .execute()
    )

    df = pd.DataFrame(response.data)

    if not df.empty:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")

    return df


@st.cache_data(ttl=60)
def cargar_observaciones():
    response = (
        supabase
        .table("observaciones")
        .select("*")
        .execute()
    )

    df = pd.DataFrame(response.data)

    if not df.empty:
        df.columns = df.columns.str.strip()

    return df

with tab3:
    if "observacion_ok" not in st.session_state:
        st.session_state.observacion_ok = False
        
    st.session_state.saving = False

    trab_df = cargar_trabajadores()
    lista_trabajadores_semanal = (
        trab_df[trab_df["estado"] == "activo"]["trabajador"]
        .tolist()
    )

    if "supervisor_ok" not in st.session_state:
        st.session_state.supervisor_ok = False

    if not st.session_state.supervisor_ok:

        st.title("🔒 Acceso Seguimiento")

        clave = st.text_input("Ingrese clave", type="password")

        if st.button("Entrar"):

            if clave == st.secrets["CLAVE_SUPERVISOR"]:
                st.session_state.supervisor_ok = True
                st.rerun()
            else:
                st.error("Clave incorrecta")

        st.stop()

    st.title("👨‍💼 Seguimiento")
    
    st.info("Panel de control de actividades (seguimiento)")

    # =========================
    # DATOS
    # =========================

    actividades_df = cargar_actividades()
    actividades_df["fecha"] = pd.to_datetime(actividades_df["fecha"], errors="coerce")

    lista_trabajadores = lista_trabajadores_semanal

    # =========================
    # FILTROS
    # =========================

    col1, col2, col3 = st.columns(3)

    with col1:
        filtro_trabajador = st.selectbox("👤 Trabajador", ["Todos"] + lista_trabajadores)

    with col2:
        meses = {
            "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4,
            "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8,
            "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12
        }
        filtro_mes = st.selectbox("📅 Mes", ["Todos"] + list(meses.keys()))

    with col3:
        lunes_base = st.date_input("📆 Lunes de la semana", value=None)

    if filtro_trabajador != "Todos" and lunes_base is None:
        st.warning("📆 Selecciona un lunes para ver las actividades")

    # =========================
    # FILTRO DATOS
    # =========================

    df = actividades_df
    df = df[df["estado"] != "inactivo"]
    if filtro_trabajador == "Todos" or lunes_base is None:
        df = df.iloc[0:0]
    else:
        df = df[df["trabajador"] == filtro_trabajador]
        lunes = lunes_base
        dias = pd.date_range(lunes, periods=5)
        df = df[df["fecha"].dt.date.isin(dias.date)]

    # =========================
    # EXPORTAR
    # =========================

    if not df.empty:

        df_excel = df.copy()
        output = BytesIO()

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_excel.to_excel(writer, index=False, sheet_name="Supervision")

        st.download_button(
            "📥 Descargar Excel",
            data=output.getvalue(),
            file_name=f"supervision_{filtro_trabajador}_{lunes_base}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        # =========================
        # EXPORTAR HISTORIAL COMPLETO
        # =========================

        st.divider()

        st.subheader("📚 Historial completo")

        if st.button("📥 Generar Excel histórico completo"):

            historial_df = cargar_actividades()

            historial_df["fecha"] = (
                historial_df["fecha"]
                .astype(str)
            )

            output_historial = BytesIO()

            with pd.ExcelWriter(
                output_historial,
                engine="openpyxl"
            ) as writer:

                historial_df.to_excel(
                    writer,
                    index=False,
                    sheet_name="Historial"
                )

            st.download_button(
                "⬇️ Descargar historial completo",
                data=output_historial.getvalue(),
                file_name="historial_completo_actividades.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    # =========================
    # LAYOUT
    # =========================

    col_izq, col_der = st.columns([2, 1])

    with col_izq:

        st.subheader("📋 Actividades")

        if df.empty:
            st.info("No hay actividades con los filtros seleccionados")

        else:

            df = df.sort_values("fecha")

            for trabajador in df["trabajador"].unique():

                st.markdown(f"## 👤 {trabajador}")

                df_trab = df[df["trabajador"] == trabajador]
                fechas_unicas = sorted(df_trab["fecha"].dt.date.unique())

                for fecha in fechas_unicas:

                    fecha_dt = pd.to_datetime(fecha)
                    st.markdown(f"### 📅 {fecha_dt.strftime('%Y/%m/%d')} ({fecha_dt.day_name()})")

                    df_dia = df_trab[df_trab["fecha"].dt.date == fecha]

                    for _, row in df_dia.iterrows():

                        col1, col2 = st.columns([6, 2])

                        with col1:
                            st.write(f"• {row['actividad']}")

                        with col2:

                            nuevo_estado = st.selectbox(
                                "estado",
                                ["No iniciado", "En proceso", "Concluido"],
                                index=["No iniciado", "En proceso", "Concluido"].index(row["estado"])
                                if row["estado"] in ["No iniciado", "En proceso", "Concluido"]
                                else 0,
                                key=f"estado_{row['id']}_{row.name}"
                            )

                            estado_color = {
                                "No iniciado": "🔴",
                                "En proceso": "🟡",
                                "Concluido": "🔵"
                            }

                            st.write(estado_color.get(nuevo_estado, "🔴"))

        st.divider()

        # =========================
        # GUARDAR
        # =========================

        if st.button("💾 Guardar cambios"):

            for _, row in df.iterrows():

                estado_actual = st.session_state.get(
                    f"estado_{row['id']}_{row.name}",
                    row["estado"]
                )

                actividades_df.loc[
                    actividades_df["id"] == row["id"],
                    "estado"
                ] = estado_actual

            for _, row in df.iterrows():
                estado_actual = st.session_state.get(
                    f"estado_{row['id']}_{row.name}",
                    row["estado"]
                )

                supabase.table("actividades").update({
                    "estado": estado_actual
                }).eq("id", row["id"]).execute()

            st.cache_data.clear()
            st.success("✅ Cambios guardados correctamente")

        st.divider()

        # =========================
        # OBSERVACIONES
        # =========================

        obs_df = cargar_observaciones()
        observacion_actual = ""

        if filtro_trabajador != "Todos" and lunes_base is not None:

            semana_actual = lunes_base.isocalendar()[1]
            anio_actual = lunes_base.year

            obs_encontrada = obs_df[
                (obs_df["trabajador"] == filtro_trabajador) &
                (obs_df["semana"].astype(int) == semana_actual) &
                (obs_df["anio"].astype(int) == anio_actual)
            ]

            if not obs_encontrada.empty:
                observacion_actual = obs_encontrada.iloc[0]["observacion"]

        observacion_texto = st.text_area(
            "Escribe la observación del supervisor",
            value=observacion_actual,
            height=150
        )
        if st.session_state.observacion_ok:
            st.success("✅ Observación guardada correctamente.")
            st.session_state.observacion_ok = False
        if st.button("💾 Guardar observación"):

            if filtro_trabajador == "Todos":
                st.warning("Selecciona un trabajador")
                st.stop()

            if lunes_base is None:
                st.warning("Selecciona una semana")
                st.stop()

            semana_actual = lunes_base.isocalendar()[1]
            anio_actual = lunes_base.year

            obs_existente = obs_df[
                (obs_df["trabajador"] == filtro_trabajador) &
                (obs_df["semana"].astype(int) == semana_actual) &
                (obs_df["anio"].astype(int) == anio_actual)
            ]

            if obs_existente.empty:

                supabase.table("observaciones").insert({
                    "trabajador": filtro_trabajador,
                    "semana": semana_actual,
                    "anio": anio_actual,
                    "observacion": observacion_texto,
                    "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }).execute()

            else:

                supabase.table("observaciones").update({
                    "observacion": observacion_texto
                }).eq("trabajador", filtro_trabajador)\
                .eq("semana", semana_actual)\
                .eq("anio", anio_actual)\
                .execute()

            st.cache_data.clear()
            st.session_state.observacion_ok = True
            st.rerun()
