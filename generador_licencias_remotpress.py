import streamlit as st
import hashlib
from datetime import datetime, timedelta

USUARIO = "dasent"
CLAVE = "20171556"

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

st.title("🔑 Generador de Licencias REMOTPRESS")

if not st.session_state["autenticado"]:
    st.write("**Acceso restringido. Solo usuarios autorizados.**")
    usuario = st.text_input("Usuario:")
    clave = st.text_input("Contraseña:", type="password")
    login = st.button("Iniciar sesión")

    if login:
        if usuario == USUARIO and clave == CLAVE:
            st.session_state["autenticado"] = True
            st.success("¡Acceso concedido! Vuelve a cargar la página si no ves el generador abajo.")
        else:
            st.error("Usuario o contraseña incorrectos.")
    st.stop()

st.success(f"¡Bienvenido, {USUARIO}! Acceso seguro concedido.")

DATE_FORMAT = "%Y-%m-%d"

def generate_license_key(machine_hash, expiry):
    fecha = expiry.replace("-", "")
    secret = "REMOTPRESS2024"
    raw = machine_hash + secret + fecha
    key_hash = hashlib.sha256(raw.encode()).hexdigest().upper()
    return f"REMOT-{fecha}-{key_hash}"

st.write("Genera licencias para RemotPress fácil, desde tu teléfono o PC.")

machine_hash = st.text_input("Código de instalación (hash):")
dias = st.number_input("¿Cuántos días de licencia?", min_value=1, value=30, step=1)

if st.button("Generar Licencia"):
    if not machine_hash.strip():
        st.warning("Debes ingresar el código de instalación.")
    else:
        fecha_expira = (datetime.now() + timedelta(days=int(dias))).strftime(DATE_FORMAT)
        key = generate_license_key(machine_hash.strip().upper(), fecha_expira)
        st.success(f"=== LICENCIA GENERADA ===\n\nKEY:    {key}\nExpira: {fecha_expira}")
        st.code(key, language="none")
        st.info("¡La clave se muestra arriba! Puedes copiarla y compartirla donde la necesites.")

if st.button("Cerrar sesión"):
    st.session_state["autenticado"] = False
    st.warning("Sesión cerrada. Recarga la página para volver a iniciar sesión.")
    st.stop()
