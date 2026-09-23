import os
import json
import requests
import UnityPy
from io import BytesIO

# Configuración
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
STATE_FILE = "vistos.json"
RUST_DIR = "rust_staging"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return set(json.load(f))
        except json.JSONDecodeError:
            print(f"Advertencia: El archivo {STATE_FILE} estaba corrupto o vacío. Iniciando lista limpia.")
            return set()
    return set()

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(list(state), f)

def send_to_discord(name, img_bytes):
    # Formato elegante del Embed para nuevos assets
    payload = {
        "embeds": [{
            "title": f"🆕 Nuevo Asset Detectado: `{name}`",
            "description": "Se ha añadido un nuevo recurso a la rama Staging.",
            "color": 8302335, # Color azul verdoso
            "footer": {"text": "Rust Staging Dataminer • GitHub Actions"}
        }]
    }
    
    files = {
        "file": (f"{name}.png", img_bytes, "image/png")
    }
    
    payload["embeds"][0]["thumbnail"] = {"url": f"attachment://{name}.png"}
    
    response = requests.post(WEBHOOK_URL, data={"payload_json": json.dumps(payload)}, files=files)
    
    if response.status_code in (200, 204):
        print(f"Enviado con éxito: {name}")
    else:
        print(f"Error al enviar {name}: {response.status_code}")

def send_initialization_message(count):
    # Mensaje único para avisarte de que la primera pasada ha terminado
    payload = {
        "embeds": [{
            "title": "✅ Dataminer Inicializado",
            "description": f"Se ha creado la base de datos inicial con **{count}** assets existentes de Rust.\n\nEl bot está al día. A partir de ahora, solo recibirás notificaciones cuando los desarrolladores añadan contenido nuevo.",
            "color": 3066993, # Color verde
            "footer": {"text": "Rust Staging Dataminer • GitHub Actions"}
        }]
    }
    requests.post(WEBHOOK_URL, json=payload)

def main():
    if not WEBHOOK_URL:
        print("Error: DISCORD_WEBHOOK no está configurado.")
        return

    vistos = load_state()
    is_first_run = len(vistos) == 0 # Detectamos si es la primera ejecución
    nuevos_encontrados = 0

    print("Buscando archivos de Unity (.bundle y .assets)...")
    if is_first_run:
        print("--- MODO INICIALIZACIÓN ---")
        print("Se registrarán todos los assets actuales sin enviarlos a Discord para evitar spam y ahorrar tiempo.")
    
    archivos_unity = []
    for root, dirs, files in os.walk(RUST_DIR):
        for file in files:
            if file.endswith(".bundle") or file.endswith(".assets"):
                archivos_unity.append(os.path.join(root, file))

    print(f"Se encontraron {len(archivos_unity)} archivos de Unity. Cargando...")
    env = UnityPy.load(*archivos_unity)

    for obj in env.objects:
        if obj.type.name in ["Texture2D", "Sprite"]:
            data = obj.read()
            name = getattr(data, "name", getattr(data, "m_Name", None))
            
            if name and ("icon" in name.lower() or "item" in name.lower()):
                if name not in vistos:
                    if is_first_run:
                        # Modo Inicialización: Lo guardamos en memoria rapidísimo, sin enviar imágenes
                        vistos.add(name)
                    else:
                        # Modo Normal (ejecuciones futuras): Extraer y notificar
                        print(f"Nuevo asset encontrado: {name}")
                        try:
                            img = data.image
                            img_byte_arr = BytesIO()
                            img.save(img_byte_arr, format='PNG')
                            
                            send_to_discord(name, img_byte_arr.getvalue())
                            vistos.add(name)
                            nuevos_encontrados += 1
                        except Exception as e:
                            print(f"Error procesando la imagen {name}: {e}")
                        
                        if nuevos_encontrados >= 10:
                            print("Límite de 10 assets alcanzado.")
                            break

    save_state(vistos)
    
    # Si fue la primera ejecución, mandamos el aviso de que ya terminó de escanear todo
    if is_first_run:
        print(f"Inicialización completada. {len(vistos)} assets registrados.")
        send_initialization_message(len(vistos))

if __name__ == "__main__":
    main()
