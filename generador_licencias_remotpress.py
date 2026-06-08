
# -*- coding: utf-8 -*-
"""
GENERADOR REMOTPRESS — CLÁSICA / PRO + QR (Instalación y Licencia)
- Login por usuarios (incluye admin)
- Genera KEY:
    CLÁSICA: REMOT-YYYYMMDD-HASH
    PRO:     REMOTPRO-YYYYMMDD-HASH
- QR:
    * Lee QR de instalación (imagen o cámara)
    * Muestra/guarda/copia QR de licencia
Requisitos:
    pip install PyQt5 opencv-python qrcode pillow
"""

import sys, os, json, hashlib, re, io
from datetime import datetime, timedelta

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QGroupBox, QSpinBox, QComboBox, QTextEdit,
    QMessageBox, QDialog, QGridLayout, QFileDialog, QCheckBox
)

# ========= USUARIOS =========
# La información de los usuarios se gestiona a través de un archivo JSON para
# permitir su administración sin modificar el código. Cada usuario está
# representado por un diccionario con las siguientes claves:
#   clave     : contraseña del usuario.
#   admin     : indica si el usuario es administrador.
#   activo    : True si el usuario puede iniciar sesión, False para bloquearlo.
#   planes    : lista de tipos de licencias permitidos (por ejemplo ["CLASICA", "PRO"]).
#   duraciones: lista de duraciones en meses que puede generar (por ejemplo [1, 3, 12]).
#   limites   : límites de licencias por duración (meses). Un diccionario donde la clave es el número de meses y
#               el valor es el número máximo de licencias que puede generar para esa duración.

USERS_FILE_NAME = "usuarios.json"

def _users_path() -> str:
    """Devuelve la ruta donde se almacena el archivo de usuarios. Similar a _state_path."""
    base = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(base, USERS_FILE_NAME)
    try:
        # comprobar acceso de escritura
        with open(candidate + ".tmp", "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(candidate + ".tmp")
        return candidate
    except Exception:
        try:
            folder = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "RemotPress")
            os.makedirs(folder, exist_ok=True)
            return os.path.join(folder, USERS_FILE_NAME)
        except Exception:
            return candidate

def load_users() -> dict:
    """Carga la lista de usuarios desde el archivo JSON. Si no existe, crea un archivo con valores por defecto."""
    # configuración por defecto
    default_users = {
        "dasent": {
            "clave": "20171556",
            "admin": True,
            "activo": True,
            "planes": ["CLASICA", "PRO"],
            # El administrador puede generar cualquier duración; por claridad se definen todas.
            "duraciones": [1, 2, 3, 4, 5, 12],
            "limites": {},
        },
        "tcnomatic": {
            "clave": "121212",
            "admin": False,
            "activo": True,
            "planes": ["CLASICA"],
            # Duraciones permitidas en meses
            "duraciones": [1, 2, 3, 4, 5, 12],
            # Límite de licencias por duración en meses; estos valores se pueden ajustar para cada usuario.
            "limites": {1: 30, 2: 30, 3: 30, 4: 30, 5: 30, 12: 30},
        },
    }
    path = _users_path()
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                # Asegurarse de convertir claves y valores a los tipos esperados
                for u, info in data.items():
                    # convertir duraciones a enteros
                    if isinstance(info.get("duraciones"), list):
                        nuevas_duraciones = []
                        for d in info["duraciones"]:
                            try:
                                nuevas_duraciones.append(int(d))
                            except Exception:
                                continue
                        info["duraciones"] = nuevas_duraciones
                    # convertir claves de límites a enteros
                    if isinstance(info.get("limites"), dict):
                        new_limits = {}
                        for k, v in info["limites"].items():
                            try:
                                key_int = int(k)
                            except Exception:
                                try:
                                    key_int = int(float(k))
                                except Exception:
                                    continue
                            new_limits[key_int] = v
                        info["limites"] = new_limits
                return data
    except Exception:
        pass
    # Si no existe el archivo, escribir los valores por defecto
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_users, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return default_users

def save_users(users: dict) -> None:
    """Guarda la estructura de usuarios en el archivo JSON."""
    path = _users_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# Funciones auxiliares para administrar usuarios
def block_user(username: str) -> bool:
    """Bloquea (desactiva) a un usuario estableciendo 'activo' en False. Devuelve True si se modificó."""
    users = load_users()
    if username in users:
        users[username]["activo"] = False
        save_users(users)
        return True
    return False

def unblock_user(username: str) -> bool:
    """Desbloquea (activa) a un usuario estableciendo 'activo' en True. Devuelve True si se modificó."""
    users = load_users()
    if username in users:
        users[username]["activo"] = True
        save_users(users)
        return True
    return False

def delete_user(username: str) -> bool:
    """Elimina a un usuario del archivo de usuarios. Devuelve True si se eliminó."""
    users = load_users()
    if username in users:
        del users[username]
        save_users(users)
        return True
    return False

# Se cargará en tiempo de ejecución mediante load_users()
USUARIOS = {}

# ========= SECRETOS (deben coincidir con RemotPress) =========
SECRET_CLASSIC = "REMOTPRESS2024"
SECRET_PRO = "REMOTPRESS2024_PRO"

# ========= PERSISTENCIA =========
STATE_FILE_NAME = "licencias_state.json"
REGISTRY_FILE_NAME = "licencias_registry.json"

def _state_path() -> str:
    # Preferir el mismo folder del script; fallback a AppData si no se puede escribir ahí
    base = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(base, STATE_FILE_NAME)
    try:
        # test write access
        with open(candidate + ".tmp", "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(candidate + ".tmp")
        return candidate
    except Exception:
        try:
            folder = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "RemotPress")
            os.makedirs(folder, exist_ok=True)
            return os.path.join(folder, STATE_FILE_NAME)
        except Exception:
            return candidate

def load_state() -> dict:
    default = {"contadores_usuarios": {}}
    p = _state_path()
    try:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data.setdefault("contadores_usuarios", {})
                if not isinstance(data["contadores_usuarios"], dict):
                    data["contadores_usuarios"] = {}
                return data
    except Exception:
        pass
    return default

def save_state(state: dict) -> None:
    p = _state_path()
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _registry_path() -> str:
    """Registro local de licencias emitidas para respaldo/Streamlit."""
    base = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(base, REGISTRY_FILE_NAME)
    try:
        with open(candidate + ".tmp", "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(candidate + ".tmp")
        return candidate
    except Exception:
        try:
            folder = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "RemotPress")
            os.makedirs(folder, exist_ok=True)
            return os.path.join(folder, REGISTRY_FILE_NAME)
        except Exception:
            return candidate


def load_license_registry() -> dict:
    default = {"licenses": {}}
    p = _registry_path()
    try:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data.setdefault("licenses", {})
                if not isinstance(data["licenses"], dict):
                    data["licenses"] = {}
                return data
    except Exception:
        pass
    return default


def save_license_registry(registry: dict) -> None:
    p = _registry_path()
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def register_generated_license(key: str, machine_hash: str, plan: str, expiry: str, username: str = "") -> None:
    """Guarda cada KEY emitida para poder usarla como respaldo en Streamlit/API."""
    try:
        registry = load_license_registry()
        k = (key or "").strip().upper()
        registry.setdefault("licenses", {})[k] = {
            "key": k,
            "machine_hash": (machine_hash or "").strip().upper(),
            "plan": (plan or "CLASICA").strip().upper(),
            "fecha_caducidad": expiry,
            "estado": "activa",
            "activa": True,
            "created_by": username or "",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        save_license_registry(registry)
    except Exception:
        pass

# ========= LICENCIAS =========
def generate_license_key(machine_hash: str, expiry_date_str: str, plan: str = "CLASICA") -> str:
    """
    - CLASICA: REMOT-YYYYMMDD-HASH
    - PRO:     REMOTPRO-YYYYMMDD-HASH
    """
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

# ========= QR (OpenCV) =========
def _qr_decode_from_image(path: str) -> str:
    try:
        import cv2
        img = cv2.imread(path)
        if img is None:
            return ""
        det = cv2.QRCodeDetector()
        data, _, _ = det.detectAndDecode(img)
        return (data or "").strip()
    except Exception:
        return ""

def _extract_hex_hash(payload: str) -> str:
    """
    Acepta:
      - 'RP|INSTALL|<hash>'
      - hash directo en hex
      - textos que contengan un hash largo
    """
    if not payload:
        return ""
    s = payload.strip()

    # Formato RP|
    if s.startswith("RP|"):
        parts = s.split("|")
        if len(parts) >= 3 and parts[1].upper() in ("INSTALL", "INST", "CODE", "HASH"):
            s = parts[2].strip()

    # Buscar el hex más largo (32..128)
    candidates = re.findall(r"[A-Fa-f0-9]{32,128}", s)
    if not candidates:
        return ""
    candidates.sort(key=len, reverse=True)
    return candidates[0].upper()

def _extract_key_from_payload(payload: str) -> str:
    """
    Acepta:
      - 'RP|LIC|REMOT...'
      - key directa
    """
    if not payload:
        return ""
    s = payload.strip()
    if s.startswith("RP|"):
        parts = s.split("|")
        if len(parts) >= 3 and parts[1].upper() in ("LIC", "LICENSE", "KEY"):
            s = parts[2].strip()
    # normalizar espacios
    s = s.replace("\n", " ").strip()
    m = re.search(r"\b(REMOTPRO|REMOT)-\d{8}-[A-F0-9]{64}\b", s, flags=re.I)
    return m.group(0).upper() if m else ""

# ========= UI: QR dialog (mostrar) =========
class QRShowDialog(QDialog):
    def __init__(self, title: str, payload: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        self.lbl = QLabel()
        self.lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl)

        btns = QHBoxLayout()
        self.btn_copy = QPushButton("Copiar QR")
        self.btn_save = QPushButton("Guardar...")
        self.btn_close = QPushButton("Cerrar")
        btns.addWidget(self.btn_copy)
        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_close)
        layout.addLayout(btns)

        self._payload = payload
        self._img = self._make_qr_image(payload)
        if self._img is not None:
            self.lbl.setPixmap(QPixmap.fromImage(self._img).scaled(280, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.lbl.setText("No se pudo generar el QR.")

        self.btn_close.clicked.connect(self.reject)
        self.btn_copy.clicked.connect(self.copy_qr)
        self.btn_save.clicked.connect(self.save_qr)

    def _make_qr_image(self, payload: str):
        try:
            import qrcode
            from PIL import Image

            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=2,
            )
            qr.add_data(payload)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            data = buf.getvalue()

            qimg = QImage.fromData(data, "PNG")
            return qimg
        except Exception:
            return None

    def copy_qr(self):
        if self._img is None:
            return
        QApplication.clipboard().setImage(self._img)
        QMessageBox.information(self, "QR", "QR copiado al portapapeles.")

    def save_qr(self):
        if self._img is None:
            return
        fn, _ = QFileDialog.getSaveFileName(self, "Guardar QR", "qr.png", "PNG (*.png)")
        if not fn:
            return
        ok = self._img.save(fn, "PNG")
        if ok:
            QMessageBox.information(self, "QR", "QR guardado.")
        else:
            QMessageBox.warning(self, "QR", "No se pudo guardar el QR.")

# ========= UI: QR scan por cámara (selector simple y rápido) =========
class QRScanCameraDialog(QDialog):
    """
    Ventana de escaneo por cámara usando OpenCV.
    - Selecciona cámara
    - Abre rápido
    - Escanea y cierra al detectar QR
    """
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(520)
        self.setMinimumHeight(420)
        self.result = ""

        layout = QVBoxLayout(self)

        # selector de cámara
        row = QHBoxLayout()
        row.addWidget(QLabel("Cámara:"))
        self.cmb = QComboBox()
        self._cam_indices = self._list_cameras()
        for label, idx in self._cam_indices:
            self.cmb.addItem(label, idx)
        row.addWidget(self.cmb, 1)
        self.btn_start = QPushButton("Iniciar")
        self.btn_stop = QPushButton("Detener")
        self.btn_stop.setEnabled(False)
        row.addWidget(self.btn_start)
        row.addWidget(self.btn_stop)
        layout.addLayout(row)

        self.view = QLabel("Listo para escanear.")
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setStyleSheet("background:#111; color:#EEE; border-radius:8px; padding:8px;")
        self.view.setMinimumHeight(300)
        layout.addWidget(self.view, 1)

        self.btn_cancel = QPushButton("Cancelar")
        layout.addWidget(self.btn_cancel)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_start.clicked.connect(self.start)
        self.btn_stop.clicked.connect(self.stop)

        self._cap = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        try:
            import cv2
            self._det = cv2.QRCodeDetector()
        except Exception:
            self._det = None

    def _list_cameras(self):
        cams = []
        # Intentar Qt Multimedia (nombres bonitos)
        try:
            from PyQt5.QtMultimedia import QCameraInfo
            infos = QCameraInfo.availableCameras()
            for i, info in enumerate(infos):
                name = info.description() or f"Cámara {i}"
                cams.append((name, i))
        except Exception:
            pass

        # Fallback
        if not cams:
            cams = [(f"Cámara {i}", i) for i in range(0, 5)]
        return cams

    def start(self):
        if self._det is None:
            QMessageBox.warning(self, "Cámara", "No se pudo inicializar el detector QR.")
            return
        cam_index = int(self.cmb.currentData())
        self.view.setText("Abriendo cámara...\nSi tarda, prueba otra cámara en el selector.")
        QApplication.processEvents()

        try:
            import cv2
            cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(cam_index)
            if not cap.isOpened():
                QMessageBox.warning(self, "Cámara", "No se pudo abrir la cámara.\nPrueba otra cámara en el selector.")
                return
            self._cap = cap
        except Exception:
            QMessageBox.warning(self, "Cámara", "No se pudo abrir la cámara.\nPrueba otra cámara en el selector.")
            return

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.view.setText("Buscando QR...")
        self._timer.start(30)

    def stop(self):
        self._timer.stop()
        try:
            if self._cap is not None:
                self._cap.release()
        except Exception:
            pass
        self._cap = None
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.view.setText("Detenido.")

    def _tick(self):
        if self._cap is None:
            return
        try:
            import cv2
            ok, frame = self._cap.read()
            if not ok or frame is None:
                return

            data, bbox, _ = self._det.detectAndDecode(frame)
            if data:
                self.result = data.strip()
                self.stop()
                self.accept()
                return

            # preview
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pix = QPixmap.fromImage(qimg).scaled(self.view.width(), self.view.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.view.setPixmap(pix)
        except Exception:
            # no reventar
            return

    def closeEvent(self, event):
        self.stop()
        super().closeEvent(event)

# ========= UI: Administer Users =========
class UserAdminDialog(QDialog):
    """
    Diálogo de administración de usuarios. Permite crear, editar, bloquear/desbloquear
    y eliminar usuarios, así como configurar sus permisos de planes y duraciones.
    Los cambios se guardan en el archivo JSON de usuarios al aceptar.
    """
    def __init__(self, parent=None, state: dict = None):
        super().__init__(parent)
        self.setWindowTitle("Administrar usuarios")
        # ancho suficiente para mostrar bien los componentes
        self.setMinimumWidth(520)

        # Hacer este diálogo modal para que la ventana principal no pueda usarse simultáneamente
        self.setWindowModality(Qt.ApplicationModal)

        # Estado de licencias (contador) para mostrar usados/restantes
        self.state = state or load_state()

        # cargar usuarios en memoria
        self.users = load_users()
        self.original_username = None  # para identificar cambios en nombre

        layout = QVBoxLayout(self)

        # selección de usuario
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Usuario:"))
        self.user_select = QComboBox()
        self.user_select.addItem("(Nuevo usuario)", "__new__")
        for u in sorted(self.users.keys()):
            self.user_select.addItem(u, u)
        top_row.addWidget(self.user_select, 1)
        layout.addLayout(top_row)

        # formulario de edición
        form = QFormLayout()
        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.admin_check = QCheckBox("Administrador")
        self.active_check = QCheckBox("Activo")
        # planes
        plan_layout = QHBoxLayout()
        self.plan_clasica = QCheckBox("CLÁSICA")
        self.plan_pro = QCheckBox("PRO")
        plan_layout.addWidget(self.plan_clasica)
        plan_layout.addWidget(self.plan_pro)
        # duraciones (lista separada por comas)
        self.durations_edit = QLineEdit()
        self.durations_edit.setPlaceholderText("Ejemplo: 1,3,12")
        # grupo de límites por duración (cada fila mostrará también usados y restantes)
        self.limits_groupbox = QGroupBox("Límites por duración")
        self.limits_layout = QVBoxLayout()
        self.limits_groupbox.setLayout(self.limits_layout)

        form.addRow("Nombre de usuario:", self.username_edit)
        form.addRow("Contraseña:", self.password_edit)
        form.addRow("Rol:", self.admin_check)
        form.addRow("Estado:", self.active_check)
        form.addRow("Planes permitidos:", plan_layout)
        form.addRow("Duraciones (meses):", self.durations_edit)
        layout.addLayout(form)
        # añadir grupo de límites debajo del formulario
        layout.addWidget(self.limits_groupbox)

        # botones
        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("Guardar")
        self.btn_delete = QPushButton("Eliminar")
        self.btn_cancel = QPushButton("Cancelar")
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_delete)
        btn_row.addWidget(self.btn_cancel)
        layout.addLayout(btn_row)

        # eventos
        self.user_select.currentIndexChanged.connect(self.on_user_selected)
        self.durations_edit.editingFinished.connect(self.update_limits_fields)
        self.btn_save.clicked.connect(self.save_user)
        self.btn_delete.clicked.connect(self.delete_user_clicked)
        self.btn_cancel.clicked.connect(self.reject)

        # cargar datos del primer item
        self.on_user_selected()

    def showEvent(self, event):
        """
        Al mostrar el diálogo se centra en la pantalla o respecto al padre para evitar
        que aparezca montado sobre la ventana principal.
        """
        super().showEvent(event)
        # ajustar tamaño según contenido
        self.adjustSize()
        # centrar respecto al padre o a la pantalla
        try:
            if self.parent() is not None:
                parent_geo = self.parent().frameGeometry()
                center_pt = parent_geo.center()
            else:
                screen = QApplication.primaryScreen()
                center_pt = screen.availableGeometry().center() if screen else None
            if center_pt:
                geo = self.frameGeometry()
                geo.moveCenter(center_pt)
                self.move(geo.topLeft())
        except Exception:
            pass

    def on_user_selected(self):
        """Carga los datos del usuario seleccionado en los campos de edición."""
        key = self.user_select.currentData()
        if key == "__new__":
            # nuevo usuario: limpiar campos
            self.original_username = None
            self.username_edit.setText("")
            self.password_edit.setText("")
            self.admin_check.setChecked(False)
            self.active_check.setChecked(True)
            self.plan_clasica.setChecked(True)
            self.plan_pro.setChecked(False)
            self.durations_edit.setText("1,3,6,12")
            self.update_limits_fields()  # generará spinboxes por defecto
            self.btn_delete.setEnabled(False)
        else:
            self.original_username = key
            info = self.users.get(key, {})
            self.username_edit.setText(key)
            self.password_edit.setText(info.get("clave", ""))
            self.admin_check.setChecked(bool(info.get("admin", False)))
            self.active_check.setChecked(bool(info.get("activo", True)))
            plans = [p.upper() for p in info.get("planes", [])]
            self.plan_clasica.setChecked("CLASICA" in plans)
            self.plan_pro.setChecked("PRO" in plans)
            # duraciones
            dur_list = info.get("duraciones", [])
            self.durations_edit.setText(",".join(str(m) for m in sorted(dur_list)))
            # actualizar límites
            self.update_limits_fields(load_values=True)
            self.btn_delete.setEnabled(True)

    def update_limits_fields(self, load_values: bool = False):
        """
        Actualiza el listado de límites basado en las duraciones ingresadas. También muestra cuántas
        licencias se han usado y cuántas quedan para cada duración.

        Si load_values=True, carga los límites actuales del usuario seleccionado.
        """
        # limpiar layout anterior
        while self.limits_layout.count():
            item = self.limits_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                # borrar layouts anidados
                sub = item.layout()
                while sub.count():
                    sub_item = sub.takeAt(0)
                    sw = sub_item.widget()
                    if sw:
                        sw.deleteLater()
        # reiniciar referencias a checks ilimitados
        self.unlimited_checks = {}
        # parsear duraciones
        text = self.durations_edit.text().strip()
        duraciones = []
        for part in text.split(','):
            part = part.strip()
            if not part:
                continue
            try:
                val = int(part)
                if val > 0:
                    duraciones.append(val)
            except Exception:
                continue
        duraciones = sorted(set(duraciones))
        # obtener límites actuales
        current_limits = {}
        if load_values and self.original_username and self.original_username in self.users:
            current_limits = self.users[self.original_username].get("limites", {})
        # obtener planes actuales para calcular usados
        current_plans = []
        if load_values and self.original_username and self.original_username in self.users:
            current_plans = [p.upper() for p in self.users[self.original_username].get("planes", [])]
        # preparar contadores de uso
        usage_counts = {}
        if load_values and self.original_username and self.original_username in self.users:
            counts = self.state.get("contadores_usuarios", {}).get(self.original_username, {})
            for key, cnt in counts.items():
                try:
                    dur_plan = key.split("_")
                    dur = int(dur_plan[0])
                    plan = dur_plan[1].upper() if len(dur_plan) > 1 else "CLASICA"
                    if dur not in usage_counts:
                        usage_counts[dur] = {}
                    usage_counts[dur][plan] = int(cnt)
                except Exception:
                    continue
        # almacenar estos valores en la instancia para uso posterior en update_remaining
        self._usage_counts = usage_counts
        self._current_plans = current_plans
        # crear widgets
        self.limit_spins = {}
        self.unlimited_checks = {}
        self.used_labels = {}
        self.remaining_labels = {}
        for m in duraciones:
            row = QHBoxLayout()
            # etiqueta con duración
            lbl = QLabel(f"{m} meses:")
            lbl.setMinimumWidth(70)
            row.addWidget(lbl)
            # spin para el límite
            spin = QSpinBox()
            spin.setRange(0, 10000)
            # establecer valor y estado ilimitado
            lim_val_raw = current_limits.get(m, 0)
            lim_val = int(lim_val_raw) if lim_val_raw is not None else 0
            # checkbox para ilimitado
            unlimited_check = QCheckBox("∞")
            # conector para habilitar/deshabilitar spin y actualizar restantes
            unlimited_check.stateChanged.connect(lambda state, m=m: self._on_unlimited_changed(m))
            # set initial states
            if lim_val < 0:
                unlimited_check.setChecked(True)
                spin.setValue(0)
                spin.setEnabled(False)
            else:
                unlimited_check.setChecked(False)
                spin.setValue(lim_val)
                spin.setEnabled(True)
            # conectar spin para actualizar restantes
            spin.valueChanged.connect(lambda val, m=m: self.update_remaining(m))
            row.addWidget(spin)
            row.addWidget(unlimited_check)
            # usados
            used_total = 0
            if load_values and self.original_username and self.original_username in self.users:
                for plan in (current_plans or ["CLASICA"]):
                    used_total += usage_counts.get(m, {}).get(plan, 0)
            used_label = QLabel(f"Usados: {used_total}")
            used_label.setMinimumWidth(80)
            row.addWidget(used_label)
            # restantes
            # determinar límite efectivo para mostrar restantes
            if lim_val < 0:
                remaining_str = "∞"
            else:
                remaining_str = str(max(lim_val - used_total, 0))
            remain_label = QLabel(f"Restantes: {remaining_str}")
            remain_label.setMinimumWidth(100)
            row.addWidget(remain_label)
            # alinear
            row.addStretch()
            self.limits_layout.addLayout(row)
            # mantener referencias
            self.limit_spins[m] = spin
            self.unlimited_checks[m] = unlimited_check
            self.used_labels[m] = used_label
            self.remaining_labels[m] = remain_label

    def _on_unlimited_changed(self, m):
        """
        Habilita o deshabilita el spin cuando se selecciona ilimitado y actualiza el valor restante.
        """
        try:
            chk = self.unlimited_checks.get(m)
            spin = self.limit_spins.get(m)
            if chk is None or spin is None:
                return
            spin.setEnabled(not chk.isChecked())
            # si se marcó ilimitado, poner valor visual en 0 pero no afecta al guardado
            if chk.isChecked():
                # no cambiar el valor del spin, solo deshabilitarlo
                pass
            self.update_remaining(m)
        except Exception:
            pass

    def update_remaining(self, m):
        """
        Recalcula el valor de restantes para la duración m según el límite actual y los usados.
        """
        try:
            used_total = 0
            # sumar usados para todas las combinaciones de planes permitidos
            for plan in (self._current_plans or ["CLASICA"]):
                used_total += self._usage_counts.get(m, {}).get(plan, 0)
            chk = self.unlimited_checks.get(m)
            spin = self.limit_spins.get(m)
            if chk is None or spin is None:
                return
            if chk.isChecked():
                remaining_str = "∞"
            else:
                lim_val = spin.value()
                if lim_val <= 0:
                    remaining_str = "0"
                else:
                    remaining_str = str(max(lim_val - used_total, 0))
            # actualizar etiqueta
            label = self.remaining_labels.get(m)
            if label is not None:
                label.setText(f"Restantes: {remaining_str}")
        except Exception:
            pass

    def save_user(self):
        """Guarda o actualiza el usuario actual en la estructura y archivo JSON."""
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        if not username:
            QMessageBox.warning(self, "Validación", "Debes ingresar un nombre de usuario.")
            return
        if not password:
            QMessageBox.warning(self, "Validación", "Debes ingresar una contraseña.")
            return
        # construir info
        info = {
            "clave": password,
            "admin": self.admin_check.isChecked(),
            "activo": self.active_check.isChecked(),
            "planes": [],
            "duraciones": [],
            "limites": {},
        }
        if self.plan_clasica.isChecked():
            info["planes"].append("CLASICA")
        if self.plan_pro.isChecked():
            info["planes"].append("PRO")
        # duraciones
        duraciones = []
        text = self.durations_edit.text().strip()
        for part in text.split(','):
            part = part.strip()
            if not part:
                continue
            try:
                val = int(part)
                if val > 0:
                    duraciones.append(val)
            except Exception:
                continue
        duraciones = sorted(set(duraciones))
        info["duraciones"] = duraciones
        # límites
        limites = {}
        for m, spin in getattr(self, 'limit_spins', {}).items():
            # si existe check ilimitado y está marcado, usar -1 como ilimitado
            unlimited_chk = None
            if hasattr(self, 'unlimited_checks'):
                unlimited_chk = self.unlimited_checks.get(m)
            if unlimited_chk is not None and unlimited_chk.isChecked():
                limites[m] = -1
            else:
                limites[m] = int(spin.value())
        info["limites"] = limites
        # actualizar dict: manejar renombrado
        if self.original_username and self.original_username != username:
            # evitar colisión con otro nombre existente
            if username in self.users and username != self.original_username:
                QMessageBox.warning(self, "Nombre duplicado", "Ya existe otro usuario con ese nombre.")
                return
            # eliminar antigua entrada
            self.users.pop(self.original_username, None)
        # asignar info
        self.users[username] = info
        # guardar
        save_users(self.users)
        QMessageBox.information(self, "Usuarios", "Usuario guardado correctamente.")
        # cerrar con éxito
        self.accept()

    def delete_user_clicked(self):
        """Elimina el usuario actualmente seleccionado."""
        if not self.original_username:
            return
        user = self.original_username
        reply = QMessageBox.question(
            self, "Eliminar", f"¿Seguro que deseas eliminar al usuario '{user}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        # eliminar
        self.users.pop(user, None)
        save_users(self.users)
        QMessageBox.information(self, "Usuarios", "Usuario eliminado.")
        self.accept()

# ========= LOGIN =========
class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔑 Acceso — Generador de Licencias REMOTPRESS")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.user_edit = QLineEdit()
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Usuario:", self.user_edit)
        form.addRow("Contraseña:", self.pass_edit)
        layout.addLayout(form)

        btns = QHBoxLayout()
        self.login_btn = QPushButton("Iniciar sesión")
        self.cancel_btn = QPushButton("Cancelar")
        btns.addWidget(self.login_btn)
        btns.addWidget(self.cancel_btn)
        layout.addLayout(btns)

        self.login_btn.clicked.connect(self.try_login)
        self.cancel_btn.clicked.connect(self.reject)

        self.logged_user = None

    def try_login(self):
        u = self.user_edit.text().strip()
        p = self.pass_edit.text().strip()
        # verificar existencia del usuario
        if u in USUARIOS:
            info = USUARIOS[u]
            # verificar si el usuario está activo
            if not info.get("activo", True):
                QMessageBox.warning(self, "Acceso denegado", "Este usuario está bloqueado.")
                return
            if p == info.get("clave"):
                self.logged_user = u
                self.accept()
                return
        # si no se cumple, mostrar error genérico
        QMessageBox.warning(self, "Acceso denegado", "Usuario o contraseña incorrectos.")

# ========= MAIN =========
class MainWindow(QMainWindow):
    def __init__(self, username: str, state: dict):
        super().__init__()
        self.username = username
        self.state = state
        self.user_info = USUARIOS[self.username]
        self.is_admin = self.user_info.get("admin", False)
        self.last_key = ""

        self.setWindowTitle("Generador de Licencias REMOTPRESS (Clásica / Pro + QR)")
        self.setMinimumWidth(720)

        central = QWidget()
        root = QVBoxLayout(central)
        self.setCentralWidget(central)

        hello = QLabel(f"¡Bienvenido, {self.username}!")
        hello.setStyleSheet("color:#0F2748; font-weight:700; font-size:14px;")
        root.addWidget(hello)

        # Panel Admin: estado de licencias de usuarios limitados
        if self.is_admin:
            # Obtener todas las duraciones únicas de los usuarios no administradores
            durations_set = set()
            for u, info in USUARIOS.items():
                if info.get("admin"):
                    continue
                # duraciones pueden venir como lista de enteros (meses)
                durations_set.update(info.get("duraciones", []))
            sorted_durations = sorted(durations_set)
            # Construir la tabla
            box = QGroupBox("Estado de licencias de usuarios limitados")
            grid = QGridLayout(box)
            row = 0
            # Encabezados
            grid.addWidget(QLabel("<b>Usuario</b>"), row, 0)
            for col, m in enumerate(sorted_durations, start=1):
                grid.addWidget(QLabel(f"<b>{m}m</b>"), row, col)
            row += 1
            # Filas por usuario
            for u, info in USUARIOS.items():
                if info.get("admin"):
                    continue
                grid.addWidget(QLabel(u), row, 0)
                # Para cada duración mostrar cuántas licencias restantes tiene
                for col, m in enumerate(sorted_durations, start=1):
                    lim = info.get("limites", {}).get(m, 0)
                    # sumar licencias usadas en todos los planes permitidos
                    total_usados = 0
                    planes_usr = [p.upper() for p in info.get("planes", ["CLASICA"])]
                    for plan in planes_usr:
                        counter_key = f"{m}_{plan}"
                        total_usados += int(self.state.get("contadores_usuarios", {}).get(u, {}).get(counter_key, 0))
                    restante = max(lim - total_usados, 0)
                    grid.addWidget(QLabel(str(restante)), row, col)
                row += 1
            # almacenar referencias para poder refrescar este panel si se actualizan usuarios
            self.admin_box = box
            self.admin_grid = grid
            self.admin_durations_sorted = sorted_durations
            root.addWidget(self.admin_box)

        # Form
        form_box = QGroupBox("Generar licencia")
        form = QFormLayout(form_box)

        self.machine_hash = QLineEdit()
        self.machine_hash.setPlaceholderText("Código de instalación (hash)")
        mh_wrap = QWidget()
        mh_row = QHBoxLayout(mh_wrap)
        mh_row.setContentsMargins(0, 0, 0, 0)
        mh_row.addWidget(self.machine_hash, 1)
        self.btn_qr_img = QPushButton("📷")
        self.btn_qr_img.setToolTip("Leer código de instalación desde imagen QR")
        self.btn_qr_cam = QPushButton("🎥")
        self.btn_qr_cam.setToolTip("Escanear código de instalación con cámara")
        mh_row.addWidget(self.btn_qr_img)
        mh_row.addWidget(self.btn_qr_cam)
        form.addRow("Código de instalación:", mh_wrap)

        if self.is_admin:
            # Administrador: selección de plan y duración en días libre
            self.plan_combo = QComboBox()
            self.plan_combo.addItems(["CLASICA", "PRO"])
            form.addRow("Plan:", self.plan_combo)

            self.dias_spin = QSpinBox()
            self.dias_spin.setRange(1, 3650)
            self.dias_spin.setValue(30)
            form.addRow("Días:", self.dias_spin)
        else:
            # Usuarios limitados: planes permitidos y duraciones en meses
            self.allowed_plans = [p.upper() for p in self.user_info.get("planes", ["CLASICA"])]
            if len(self.allowed_plans) > 1:
                self.plan_combo = QComboBox()
                self.plan_combo.addItems(self.allowed_plans)
                form.addRow("Plan:", self.plan_combo)
            else:
                self.plan_combo = None

            # Duraciones permitidas en meses
            self.duracion_combo = QComboBox()
            for m in sorted(self.user_info.get("duraciones", [])):
                self.duracion_combo.addItem(str(m))
            form.addRow("Duración (meses):", self.duracion_combo)

        self.btn_gen = QPushButton("Generar Licencia")
        self.btn_copy = QPushButton("Copiar KEY")
        self.btn_copy.setEnabled(False)
        self.btn_qr_key = QPushButton("QR Licencia")
        self.btn_qr_key.setEnabled(False)

        row_btn = QHBoxLayout()
        row_btn.addWidget(self.btn_gen)
        row_btn.addWidget(self.btn_copy)
        row_btn.addWidget(self.btn_qr_key)
        root.addWidget(form_box)
        root.addLayout(row_btn)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        root.addWidget(self.output)

        self.btn_gen.clicked.connect(self.on_generate)
        self.btn_copy.clicked.connect(self.copy_key)
        self.btn_qr_img.clicked.connect(self.on_read_install_qr_image)
        self.btn_qr_cam.clicked.connect(self.on_read_install_qr_camera)
        self.btn_qr_key.clicked.connect(self.on_show_license_qr)

        # En modo administrador añadir botón para gestionar usuarios
        if self.is_admin:
            self.btn_manage_users = QPushButton("Administrar usuarios")
            self.btn_manage_users.clicked.connect(self.open_user_admin)
            root.addWidget(self.btn_manage_users)

        # estilo
        self.setStyleSheet("""
            * { font-size: 13px; }
            QMainWindow { background: #F6F8FB; }
            QLabel { color: #0F2748; }
            QGroupBox { border: 1px solid #D7E4F4; border-radius: 8px; margin-top: 10px; padding-top: 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 1px 6px; color: #0F3D73; font-weight: 700; }
            QLineEdit, QComboBox, QTextEdit {
                background:#FFFFFF; color:#0F2748; border:1px solid #C5D8EE; border-radius:6px; padding:6px 8px;
                selection-background-color:#D1E9FF; selection-color:#0F2748;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus { border:1px solid #1976D2; }
            QPushButton { background:#1976D2; color:#FFF; font-weight:600; border:1px solid #1565C0; border-radius:6px; padding:7px 12px; }
            QPushButton:hover { background:#1565C0; }
            QPushButton:disabled { background:#AAB7C4; border-color:#8FA3B6; }
        """)

    # ----- acciones -----
    def on_read_install_qr_image(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Seleccionar imagen QR", "", "Imágenes (*.png *.jpg *.jpeg *.bmp)")
        if not fn:
            return
        payload = _qr_decode_from_image(fn)
        if not payload:
            QMessageBox.warning(self, "QR", "No se detectó ningún QR en la imagen.")
            return
        code = _extract_hex_hash(payload)
        if not code:
            QMessageBox.warning(self, "QR", "El QR no contiene un código de instalación válido.")
            return
        self.machine_hash.setText(code)

    def on_read_install_qr_camera(self):
        dlg = QRScanCameraDialog("Escanear QR (Instalación)", self)
        if dlg.exec_() != QDialog.Accepted:
            return
        payload = (dlg.result or "").strip()
        if not payload:
            QMessageBox.warning(self, "QR", "No se detectó ningún QR.")
            return
        code = _extract_hex_hash(payload)
        if not code:
            QMessageBox.warning(self, "QR", "El QR no contiene un código de instalación válido.")
            return
        self.machine_hash.setText(code)

    def on_show_license_qr(self):
        if not self.last_key:
            return
        payload = f"RP|LIC|{self.last_key}"
        dlg = QRShowDialog("QR de Licencia", payload, self)
        dlg.exec_()

    def copy_key(self):
        if not self.last_key:
            return
        QApplication.clipboard().setText(self.last_key)
        QMessageBox.information(self, "Copiado", "KEY copiada al portapapeles.")

    def on_generate(self):
        mh = self.machine_hash.text().strip()
        if not mh:
            QMessageBox.warning(self, "Falta dato", "Debes ingresar el código de instalación.")
            return

        # si vino con texto, extraer hash
        mh2 = _extract_hex_hash(mh) or mh.strip().upper()
        self.machine_hash.setText(mh2)
        mh = mh2

        # validar mínimamente
        if not re.fullmatch(r"[A-F0-9]{16,128}", mh):
            QMessageBox.warning(self, "Código inválido", "El código de instalación no parece válido.")
            return

        if self.is_admin:
            # Los administradores generan licencias libremente indicando días y plan
            dias = int(self.dias_spin.value())
            expiry = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
            plan = self.plan_combo.currentText().strip().upper()
            key = generate_license_key(mh, expiry, plan=plan)
            register_generated_license(key, mh, plan, expiry, self.username)
            self.last_key = key
            self.output.setPlainText(
                f"=== LICENCIA GENERADA ===\nPLAN: {plan}\nKEY: {key}\nExpira: {expiry}"
            )
            self.btn_copy.setEnabled(True)
            self.btn_qr_key.setEnabled(True)
            return

        # Usuarios no administradores: validar permisos, duración y límites
        # Determinar el plan seleccionado o el único permitido
        if hasattr(self, "plan_combo") and self.plan_combo is not None:
            plan = self.plan_combo.currentText().strip().upper()
        else:
            plan = self.allowed_plans[0]
        # Verificar que el plan está permitido
        if plan not in self.allowed_plans:
            QMessageBox.warning(self, "No permitido", "No tienes permisos para generar licencias de este tipo.")
            return

        # Duración en meses seleccionada
        try:
            meses = int(self.duracion_combo.currentText())
        except Exception:
            QMessageBox.warning(self, "Error", "Duración inválida.")
            return
        limites = self.user_info.get("limites", {})
        if meses not in limites:
            QMessageBox.warning(self, "No permitido", "No tienes permitido generar licencias para esa duración.")
            return
        # límite = 0 se interpreta como sin límite (valor ilimitado)
        limite_actual = int(limites.get(meses, 0))
        # Calcular cuántas licencias se han utilizado para esta combinación de duración y plan
        counter_key = f"{meses}_{plan}"
        usados = self.state.setdefault("contadores_usuarios", {}).setdefault(self.username, {}).get(counter_key, 0)
        # Si el límite es 0, no se permite generar licencias; si es negativo, es ilimitado
        if limite_actual == 0:
            QMessageBox.warning(self, "Límite alcanzado", "No tienes permitido generar licencias para esa duración.")
            return
        if limite_actual > 0 and int(usados) >= limite_actual:
            QMessageBox.warning(self, "Límite alcanzado", "Ya alcanzaste el límite para esa duración y plan.")
            return

        # calcular días de vencimiento (aprox.)
        dias = meses * 30
        expiry = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
        key = generate_license_key(mh, expiry, plan=plan)
        register_generated_license(key, mh, plan, expiry, self.username)
        self.last_key = key

        # incrementar contador y guardar estado
        self.state["contadores_usuarios"].setdefault(self.username, {})
        self.state["contadores_usuarios"][self.username][counter_key] = int(usados) + 1
        save_state(self.state)

        self.output.setPlainText(
            f"=== LICENCIA GENERADA ===\nPLAN: {plan}\nKEY: {key}\nExpira: {expiry}"
        )
        self.btn_copy.setEnabled(True)
        self.btn_qr_key.setEnabled(True)

        # si es administrador, refrescar panel de licencias para mostrar los nuevos totales de los usuarios
        if self.is_admin:
            try:
                self.refresh_admin_panel()
            except Exception:
                pass

    # ----- admin user management -----
    def open_user_admin(self):
        """
        Abre el diálogo de administración de usuarios. Al cerrar el diálogo y aceptar cambios,
        recarga la tabla de licencias de usuarios y actualiza la información de usuarios.
        """
        # pasar el estado de licencias para que el diálogo pueda mostrar usados/restantes
        dlg = UserAdminDialog(self, state=self.state)
        if dlg.exec_() == QDialog.Accepted:
            # Recargar usuarios y actualizar panel
            global USUARIOS
            USUARIOS = load_users()
            # Actualizar user_info del usuario logueado
            self.user_info = USUARIOS.get(self.username, {})
            # refrescar panel admin
            if hasattr(self, "admin_box"):
                self.refresh_admin_panel()

    def refresh_admin_panel(self):
        """
        Reconstruye la tabla de estado de licencias de usuarios limitada con la información actual.
        """
        # Eliminar panel existente
        if not hasattr(self, 'admin_box'):
            return
        layout = self.centralWidget().layout()
        # remove the widget
        layout.removeWidget(self.admin_box)
        self.admin_box.setParent(None)
        # recrear
        durations_set = set()
        for u, info in USUARIOS.items():
            if info.get("admin"):
                continue
            durations_set.update(info.get("duraciones", []))
        sorted_durations = sorted(durations_set)
        box = QGroupBox("Estado de licencias de usuarios limitados")
        grid = QGridLayout(box)
        row = 0
        grid.addWidget(QLabel("<b>Usuario</b>"), row, 0)
        for col, m in enumerate(sorted_durations, start=1):
            grid.addWidget(QLabel(f"<b>{m}m</b>"), row, col)
        row += 1
        state = self.state
        for u, info in USUARIOS.items():
            if info.get("admin"):
                continue
            grid.addWidget(QLabel(u), row, 0)
            for col, m in enumerate(sorted_durations, start=1):
                lim = info.get("limites", {}).get(m, 0)
                total_usados = 0
                planes_usr = [p.upper() for p in info.get("planes", ["CLASICA"])]
                for plan in planes_usr:
                    counter_key = f"{m}_{plan}"
                    total_usados += int(state.get("contadores_usuarios", {}).get(u, {}).get(counter_key, 0))
                # Si límite es negativo, se considera ilimitado; si es 0, no se permite
                lim_int = int(lim)
                if lim_int < 0:
                    restante_str = "∞"
                elif lim_int == 0:
                    # no se permite, mostrar 0 como restantes
                    restante_str = "0"
                else:
                    restante_val = max(lim_int - total_usados, 0)
                    restante_str = str(restante_val)
                grid.addWidget(QLabel(restante_str), row, col)
            row += 1
        # update references
        self.admin_box = box
        self.admin_grid = grid
        self.admin_durations_sorted = sorted_durations
        layout.insertWidget(1, self.admin_box)

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("REMOTPRESS Licencias Local")

    # cargar estado y usuarios
    state = load_state()
    users = load_users()
    # asignar a la variable global para que los diálogos puedan consultarlos
    global USUARIOS
    USUARIOS = users

    login = LoginDialog()
    if login.exec_() == QDialog.Accepted and login.logged_user:
        win = MainWindow(login.logged_user, state)
        win.show()
        sys.exit(app.exec_())
    sys.exit(0)

if __name__ == "__main__":
    main()
