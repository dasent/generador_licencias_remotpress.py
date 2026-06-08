# -*- coding: utf-8 -*-
"""
REMOTPRESS Licencias — Streamlit compatible
- Genera licencias CLÁSICA / PRO con los mismos secretos de RemotPress Taller.
- Guarda un registro local en licencias_registry.json.
- Permite activar/suspender/revocar desde la web.
- Modo verificación compatible con RemotPress:
    ?rp_api=verify&license_key=REMOT...&machine_hash=HASH

IMPORTANTE:
Streamlit Community no es una API JSON pura. Por eso imprime la respuesta entre:
RP_LICENSE_JSON_START ... RP_LICENSE_JSON_END
RemotPress Taller modificado puede leer JSON puro o este marcador si llega en HTML.
Para máxima estabilidad, usa PHP/Firebase como servidor principal y Streamlit como respaldo temporal.
"""

import os
import json
import re
import hashlib
from datetime import datetime, timedelta

import streamlit as st

APP_TITLE = "Generador de Licencias REMOTPRESS"
USERS_FILE_NAME = "usuarios.json"
STATE_FILE_NAME = "licencias_state.json"
REGISTRY_FILE_NAME = "licencias_registry.json"

SECRET_CLASSIC = "REMOTPRESS2024"
SECRET_PRO = "REMOTPRESS2024_PRO"

DEFAULT_USERS = {
    "dasent": {
        "clave": "20171556",
        "admin": True,
        "activo": True,
        "planes": ["CLASICA", "PRO"],
        "duraciones": [1, 2, 3, 4, 5, 12],
        "limites": {},
    },
    "tcnomatic": {
        "clave": "121212",
        "admin": False,
        "activo": True,
        "planes": ["CLASICA"],
        "duraciones": [1, 2, 3, 4, 5, 12],
        "limites": {"1": 30, "2": 30, "3": 30, "4": 30, "5": 30, "12": 30},
    },
}


def app_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def data_path(name: str) -> str:
    return os.path.join(app_dir(), name)


def load_json(path: str, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, type(default)) else default
    except Exception:
        pass
    return default


def save_json(path: str, data) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_users() -> dict:
    path = data_path(USERS_FILE_NAME)
    users = load_json(path, DEFAULT_USERS.copy())
    if not os.path.exists(path):
        save_json(path, users)
    return users


def load_state() -> dict:
    return load_json(data_path(STATE_FILE_NAME), {"contadores_usuarios": {}})


def save_state(state: dict) -> None:
    save_json(data_path(STATE_FILE_NAME), state)


def load_registry() -> dict:
    data = load_json(data_path(REGISTRY_FILE_NAME), {"licenses": {}})
    data.setdefault("licenses", {})
    if not isinstance(data["licenses"], dict):
        data["licenses"] = {}
    return data


def save_registry(registry: dict) -> None:
    save_json(data_path(REGISTRY_FILE_NAME), registry)


def generate_license_key(machine_hash: str, expiry_date_str: str, plan: str = "CLASICA") -> str:
    fecha = expiry_date_str.replace("-", "")
    plan = (plan or "CLASICA").strip().upper()
    if plan == "PRO":
        prefix = "REMOTPRO"
        secret = SECRET_PRO
    else:
        prefix = "REMOT"
        secret = SECRET_CLASSIC
        plan = "CLASICA"
    raw = machine_hash.upper().strip() + secret + fecha
    key_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()
    return f"{prefix}-{fecha}-{key_hash}"


def parse_license_key(key: str):
    try:
        parts = (key or "").strip().upper().split("-")
        if len(parts) < 3:
            return None, None, None
        prefix = parts[0]
        if prefix not in ("REMOT", "REMOTPRO"):
            return None, None, None
        expiry = datetime.strptime(parts[1], "%Y%m%d").date()
        plan = "PRO" if prefix == "REMOTPRO" else "CLASICA"
        return plan, expiry, "-".join(parts[2:])
    except Exception:
        return None, None, None


def verify_local_key_math(key: str, machine_hash: str) -> bool:
    plan, expiry, hash_part = parse_license_key(key)
    if not plan or not expiry or not hash_part:
        return False
    secret = SECRET_PRO if plan == "PRO" else SECRET_CLASSIC
    raw = (machine_hash or "").strip().upper() + secret + expiry.strftime("%Y%m%d")
    expected = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()
    return expected == hash_part


def register_license(key: str, machine_hash: str, plan: str, expiry: str, user: str = "admin") -> None:
    registry = load_registry()
    registry["licenses"][(key or "").strip().upper()] = {
        "key": (key or "").strip().upper(),
        "machine_hash": (machine_hash or "").strip().upper(),
        "plan": (plan or "CLASICA").strip().upper(),
        "fecha_caducidad": expiry,
        "estado": "activa",
        "activa": True,
        "created_by": user,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_registry(registry)


def response_for_license(key: str, machine_hash: str) -> dict:
    key = (key or "").strip().upper()
    machine_hash = (machine_hash or "").strip().upper()
    now = datetime.now().date()
    registry = load_registry()
    item = (registry.get("licenses") or {}).get(key)

    if item:
        expected_machine = str(item.get("machine_hash") or "").strip().upper()
        if expected_machine and machine_hash and expected_machine != machine_hash:
            return {
                "ok": False,
                "success": False,
                "activa": False,
                "estado": "limite_dispositivos",
                "error": "La licencia pertenece a otro equipo.",
                "license_key": key,
            }
        estado = str(item.get("estado") or "activa").strip().lower()
        expiry = str(item.get("fecha_caducidad") or item.get("vence") or "").strip()
        try:
            expiry_date = datetime.strptime(expiry[:10], "%Y-%m-%d").date()
        except Exception:
            expiry_date = None
        if expiry_date and expiry_date < now:
            estado = "vencida"
        active = estado in ("activa", "activo", "active", "ok", "valid", "valida", "válida")
        return {
            "ok": bool(active),
            "success": bool(active),
            "activa": bool(active),
            "estado": "activa" if active else estado,
            "plan": str(item.get("plan") or "").upper(),
            "fecha_caducidad": expiry,
            "vence": expiry,
            "dias_restantes": max(0, (expiry_date - now).days) if expiry_date else None,
            "license_key": key,
            "key": key,
            "source": "streamlit_registry",
        }

    # Si no está en registro, validamos matemáticamente para no romper licencias antiguas.
    plan, expiry_date, _ = parse_license_key(key)
    if plan and expiry_date and verify_local_key_math(key, machine_hash):
        active = expiry_date >= now
        return {
            "ok": bool(active),
            "success": bool(active),
            "activa": bool(active),
            "estado": "activa" if active else "vencida",
            "plan": plan,
            "fecha_caducidad": expiry_date.isoformat(),
            "vence": expiry_date.isoformat(),
            "dias_restantes": max(0, (expiry_date - now).days),
            "license_key": key,
            "key": key,
            "source": "streamlit_math_fallback",
        }

    return {
        "ok": False,
        "success": False,
        "activa": False,
        "estado": "no_encontrada",
        "error": "Licencia no encontrada o inválida.",
        "license_key": key,
        "source": "streamlit_registry",
    }


def get_params() -> dict:
    try:
        return dict(st.query_params)
    except Exception:
        try:
            return {k: v[0] if isinstance(v, list) and v else v for k, v in st.experimental_get_query_params().items()}
        except Exception:
            return {}


def maybe_api_mode() -> bool:
    params = get_params()
    if str(params.get("rp_api") or params.get("api") or "").lower() not in ("verify", "licencia", "license"):
        return False
    key = params.get("license_key") or params.get("key") or ""
    mh = params.get("machine_hash") or params.get("codigo_instalacion") or ""
    payload = response_for_license(key, mh)
    raw = json.dumps(payload, ensure_ascii=False)
    st.set_page_config(page_title="RemotPress License API", layout="centered")
    st.code("RP_LICENSE_JSON_START" + raw + "RP_LICENSE_JSON_END", language="json")
    st.json(payload)
    return True


def login_panel(users: dict):
    st.subheader("Acceso")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Iniciar sesión"):
        info = users.get(u)
        if info and info.get("activo", True) and p == info.get("clave"):
            st.session_state["rp_user"] = u
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")


def app_ui():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)
    users = load_users()
    state = load_state()

    if "rp_user" not in st.session_state:
        login_panel(users)
        return

    user = st.session_state["rp_user"]
    info = users.get(user, {})
    is_admin = bool(info.get("admin"))
    st.success(f"Sesión iniciada: {user}")
    if st.button("Cerrar sesión"):
        st.session_state.pop("rp_user", None)
        st.rerun()

    st.header("Generar licencia")
    machine_hash = st.text_input("Código de instalación / Machine hash").strip().upper()

    if is_admin:
        plan = st.selectbox("Plan", ["CLASICA", "PRO"])
        dias = st.number_input("Días", min_value=1, max_value=3650, value=30, step=1)
    else:
        plans = [p.upper() for p in info.get("planes", ["CLASICA"])]
        plan = st.selectbox("Plan", plans)
        durations = sorted({int(x) for x in info.get("duraciones", [1])})
        meses = st.selectbox("Duración (meses)", durations)
        dias = int(meses) * 30

    if st.button("Generar licencia"):
        if not re.fullmatch(r"[A-F0-9]{16,128}", machine_hash or ""):
            st.error("El código de instalación no parece válido.")
        else:
            expiry = (datetime.now() + timedelta(days=int(dias))).strftime("%Y-%m-%d")
            key = generate_license_key(machine_hash, expiry, plan)
            register_license(key, machine_hash, plan, expiry, user=user)
            st.code(key)
            st.success(f"Licencia generada. Expira: {expiry}")

    st.header("Registro de licencias")
    registry = load_registry()
    licenses = registry.get("licenses", {})
    search = st.text_input("Buscar KEY o equipo")
    rows = []
    for k, item in licenses.items():
        if search and search.lower() not in (k + json.dumps(item, ensure_ascii=False)).lower():
            continue
        rows.append(item)
    st.dataframe(rows, use_container_width=True)

    if is_admin:
        st.subheader("Cambiar estado")
        key_edit = st.text_input("KEY a modificar").strip().upper()
        new_estado = st.selectbox("Nuevo estado", ["activa", "suspendida", "revocada", "vencida", "bloqueada"])
        if st.button("Guardar estado"):
            registry = load_registry()
            if key_edit in registry.get("licenses", {}):
                item = registry["licenses"][key_edit]
                item["estado"] = new_estado
                item["activa"] = new_estado == "activa"
                item["updated_at"] = datetime.now().isoformat(timespec="seconds")
                save_registry(registry)
                st.success("Estado actualizado.")
            else:
                st.error("KEY no encontrada en el registro.")

    raw_registry = json.dumps(load_registry(), ensure_ascii=False, indent=2)
    st.download_button("Descargar licencias_registry.json", raw_registry, "licencias_registry.json", "application/json")

    st.info("URL de verificación para RemotPress: agrega ?rp_api=verify&license_key=KEY&machine_hash=HASH a esta app.")


def main():
    if maybe_api_mode():
        return
    app_ui()


if __name__ == "__main__":
    main()
