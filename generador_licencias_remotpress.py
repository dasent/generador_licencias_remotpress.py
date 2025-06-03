import streamlit as st
import hashlib
from datetime import datetime, timedelta

DATE_FORMAT = "%Y-%m-%d"

def generate_license_key(machine_hash, expiry):
    fecha = expiry.replace("-", "")
    secret = "REMOTPRESS2024"
    raw = machine_hash + secret + fecha
    key_hash = hashlib.sha256(raw.encode()).hexdigest().upper()
    return f"REMOT-{fecha}-{key_hash}"

st.title("🔑 Generador de Licencias REMOTPRESS")
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
