import streamlit as st
import hashlib
from datetime import datetime, timedelta

# ========== USUARIOS Y CLAVES ==========
USUARIOS = {
    "dasent": {
        "clave": "20171556",
        "admin": True
    },
    "tcnomatic": {
        "clave": "121212",
        "admin": False,
        "limites": {
            30: 30,
            180: 30,
            365: 30
        }
    }
}

# ========== CONTADORES ==========
if "contadores_usuarios" not in st.session_state:
    st.session_state["contadores_usuarios"] = {}
    for usuario, info in USUARIOS.items():
        if not info.get("admin", False):
            st.session_state["contadores_usuarios"][usuario] = {30: 0, 180: 0, 365: 0}

def show_login():
    st.title("🔑 Generador de Licencias REMOTPRESS")
    st.write("**Acceso restringido. Solo usuarios autorizados.**")
    usuario = st.text_input("Usuario:", key="usuario_login")
    clave = st.text_input("Contraseña:", type="password", key="clave_login")
    login_btn = st.button("Iniciar sesión", key="btn_login")
    if login_btn:
        if usuario in USUARIOS and clave == USUARIOS[usuario]["clave"]:
            st.session_state["autenticado"] = True
            st.session_state["usuario"] = usuario
            st.experimental_rerun()  # Hacemos un rerun aquí para limpiar la pantalla
        else:
            st.error("Usuario o contraseña incorrectos.")
            st.session_state["autenticado"] = False
            st.session_state["usuario"] = ""

def main_app():
    usuario = st.session_state["usuario"]
    admin = USUARIOS[usuario].get("admin", False)
    st.title("🔑 Generador de Licencias REMOTPRESS")
    st.success(f"¡Bienvenido, {usuario}! Acceso seguro concedido.")
    st.write("Genera licencias para RemotPress fácil, desde tu teléfono o PC.")

    # ADMIN VE CONTADORES
    if admin:
        st.markdown("### Estado de licencias de los usuarios limitados")
        for user, data in USUARIOS.items():
            if not data.get("admin", False):
                limites = data["limites"]
                usados = st.session_state["contadores_usuarios"].get(user, {30: 0, 180: 0, 365: 0})
                st.write(f"**Usuario:** {user}")
                st.write(
                    f"- 30 días: {usados[30]}/{limites[30]} usados  |  Quedan: {limites[30] - usados[30]}"
                )
                st.write(
                    f"- 180 días: {usados[180]}/{limites[180]} usados  |  Quedan: {limites[180] - usados[180]}"
                )
                st.write(
                    f"- 365 días: {usados[365]}/{limites[365]} usados  |  Quedan: {limites[365] - usados[365]}"
                )
                st.write("---")

    def generate_license_key(machine_hash, expiry):
        fecha = expiry.replace("-", "")
        secret = "REMOTPRESS2024"
        raw = machine_hash + secret + fecha
        key_hash = hashlib.sha256(raw.encode()).hexdigest().upper()
        return f"REMOT-{fecha}-{key_hash}"

    machine_hash = st.text_input("Código de instalación (hash):")
    dias = st.number_input("¿Cuántos días de licencia?", min_value=1, value=30, step=1)

    if st.button("Generar Licencia"):
        if not machine_hash.strip():
            st.warning("Debes ingresar el código de instalación.")
        else:
            if admin:
                fecha_expira = (datetime.now() + timedelta(days=int(dias))).strftime("%Y-%m-%d")
                key = generate_license_key(machine_hash.strip().upper(), fecha_expira)
                st.success(f"=== LICENCIA GENERADA ===\n\nKEY:    {key}\nExpira: {fecha_expira}")
                st.code(key, language="none")
                st.info("¡La clave se muestra arriba! Puedes copiarla y compartirla donde la necesites.")
            else:
                limites = USUARIOS[usuario]["limites"]
                usados = st.session_state["contadores_usuarios"][usuario]
                dias_seleccionados = int(dias)
                if dias_seleccionados not in limites:
                    st.error("Solo puedes generar licencias de 30, 180 o 365 días.")
                elif usados[dias_seleccionados] >= limites[dias_seleccionados]:
                    st.error(f"Ya alcanzaste el límite de {limites[dias_seleccionados]} licencias de {dias_seleccionados} días.")
                else:
                    fecha_expira = (datetime.now() + timedelta(days=dias_seleccionados)).strftime("%Y-%m-%d")
                    key = generate_license_key(machine_hash.strip().upper(), fecha_expira)
                    st.success(f"=== LICENCIA GENERADA ===\n\nKEY:    {key}\nExpira: {fecha_expira}")
                    st.code(key, language="none")
                    st.info("¡La clave se muestra arriba! Puedes copiarla y compartirla donde la necesites.")
                    st.session_state["contadores_usuarios"][usuario][dias_seleccionados] += 1
                    st.info(
                        f"Llevas {st.session_state['contadores_usuarios'][usuario][30]}/30 de 30 días, "
                        f"{st.session_state['contadores_usuarios'][usuario][180]}/30 de 180 días, "
                        f"{st.session_state['contadores_usuarios'][usuario][365]}/30 de 365 días."
                    )

    if st.button("Cerrar sesión"):
        st.session_state["autenticado"] = False
        st.session_state["usuario"] = ""
        st.experimental_rerun()

# ==== FLUJO PRINCIPAL ====
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    show_login()
else:
    main_app()
