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

def send_to_discord(name, asset_type, img_bytes=None):
    # Definir descripción según el tipo de asset
    desc_text = "Se ha añadido un nuevo recurso a la rama Staging."
    if asset_type == "AudioClip":
        desc_text = "🔊 Se ha detectado un nuevo archivo de sonido/audio."
    elif asset_type == "GameObject":
        desc_text = "📦 Se ha detectado un nuevo modelo 3D / Prefab."
    elif asset_type in ["Texture2D", "Sprite"]:
        desc_text = "🖼️ Se ha detectado una nueva textura o icono."

    # Formato elegante del Embed para nuevos assets
    payload = {
        "embeds": [{
            "title": f"🆕 Nuevo Asset Detectado: `{name}`",
            "description": desc_text,
            "color": 8302335, # Color azul verdoso
            "footer": {"text": "Rust Staging Dataminer • GitHub Actions"}
        }]
    }
    
    files = None
    if img_bytes:
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
    payload = {
        "embeds": [{
            "title": "✅ Dataminer Inicializado",
            "description": f"Se ha creado la base de datos inicial con **{count}** assets existentes de Rust (incluyendo iconos, prefabs y sonidos).\n\nEl bot está al día. A partir de ahora, solo recibirás notificaciones cuando los desarrolladores añadan contenido nuevo.",
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
    is_first_run = len(vistos) == 0
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
        # Buscamos Imágenes (Texture2D/Sprite), Modelos 3D (GameObject) y Sonidos (AudioClip)
        if obj.type.name in ["Texture2D", "Sprite", "GameObject", "AudioClip"]:
            data = obj.read()
            name = getattr(data, "name", getattr(data, "m_Name", None))
            
            if not name:
                continue

            # Filtro 1: Imágenes de iconos e ítems
            is_icon = obj.type.name in ["Texture2D", "Sprite"] and ("icon" in name.lower() or "item" in name.lower())
            
            # Filtro 2: Prefabs de cosas importantes en Rust (animales, NPCs, armas, vehículos, monumentos)
            is_prefab = obj.type.name == "GameObject" and any(keyword in name.lower() for keyword in ["npc", "animal", "monument", "vehicle", "weapon"])

            # Filtro 3: Nuevos sonidos y audios
            is_audio = obj.type.name == "AudioClip" and any(keyword in name.lower() for keyword in ["sound", "audio", "weapon", "fx", "music", "vo", "ambient"])

            if (is_icon or is_prefab or is_audio) and name not in vistos:
                if is_first_run:
                    # Modo Inicialización: Lo guardamos rapidísimo
                    vistos.add(name)
                else:
                    # Modo Normal: Extraer y notificar
                    print(f"Novedad encontrada ({obj.type.name}): {name}")
                    try:
                        if is_icon:
                            img = data.image
                            img_byte_arr = BytesIO()
                            img.save(img_byte_arr, format='PNG')
                            send_to_discord(name, obj.type.name, img_byte_arr.getvalue())
                        else:
                            # Modelo 3D o Audio, solo texto
                            send_to_discord(name, obj.type.name, None)
                        
                        vistos.add(name)
                        nuevos_encontrados += 1
                    except Exception as e:
                        print(f"Error procesando {name}: {e}")
                    
                    if nuevos_encontrados >= 10:
                        print("Límite de 10 alertas alcanzado.")
                        break

    save_state(vistos)
    
    if is_first_run:
        print(f"Inicialización completada. {len(vistos)} assets registrados.")
        send_initialization_message(len(vistos))

if __name__ == "__main__":
    main()
