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
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(list(state), f)

def send_to_discord(name, img_bytes):
    # Formato elegante del Embed (Color verde Rust)
    payload = {
        "embeds": [{
            "title": f"🆕 Nuevo Asset Detectado: `{name}`",
            "description": "Se ha añadido un nuevo recurso a la rama Staging.",
            "color": 8302335, # Color verde/azulado
            "footer": {"text": "Rust Staging Dataminer • GitHub Actions"}
        }]
    }
    
    # Preparamos la imagen para adjuntarla
    files = {
        "file": (f"{name}.png", img_bytes, "image/png")
    }
    
    # Vinculamos la imagen adjunta al embed
    payload["embeds"][0]["thumbnail"] = {"url": f"attachment://{name}.png"}
    
    # Enviamos la petición a Discord multipart/form-data
    response = requests.post(WEBHOOK_URL, data={"payload_json": json.dumps(payload)}, files=files)
    
    if response.status_code in (200, 204):
        print(f"Enviado con éxito: {name}")
    else:
        print(f"Error al enviar {name}: {response.status_code}")

def main():
    if not WEBHOOK_URL:
        print("Error: DISCORD_WEBHOOK no está configurado.")
        return

    vistos = load_state()
    nuevos_encontrados = 0

    print("Buscando archivos de Unity (.bundle y .assets)...")
    
    archivos_unity = []
    for root, dirs, files in os.walk(RUST_DIR):
        for file in files:
            if file.endswith(".bundle") or file.endswith(".assets"):
                archivos_unity.append(os.path.join(root, file))

    print(f"Se encontraron {len(archivos_unity)} archivos de Unity. Cargando...")
    # Carga exclusivamente los archivos de assets
    env = UnityPy.load(*archivos_unity)

    for obj in env.objects:
        # Los íconos pueden guardarse como Texture2D o Sprite en Unity
        if obj.type.name in ["Texture2D", "Sprite"]:
            data = obj.read()
            
            # SOLUCIÓN: Usar getattr para evitar el crasheo si el objeto no tiene la propiedad 'name'
            name = getattr(data, "name", getattr(data, "m_Name", None))
            
            if name and ("icon" in name.lower() or "item" in name.lower()):
                if name not in vistos:
                    print(f"Nuevo asset encontrado: {name}")
                    
                    try:
                        # Extraer imagen
                        img = data.image
                        img_byte_arr = BytesIO()
                        img.save(img_byte_arr, format='PNG')
                        
                        # Enviar a Discord
                        send_to_discord(name, img_byte_arr.getvalue())
                        
                        # Añadir a la base de datos local
                        vistos.add(name)
                        nuevos_encontrados += 1
                    except Exception as e:
                        print(f"Error procesando la imagen {name}: {e}")
                    
                    # Límite por ejecución (para no superar los 10 minutos ni spamear)
                    if nuevos_encontrados >= 10:
                        print("Límite de 10 assets alcanzado. El resto se procesará en la próxima ejecución.")
                        break

    save_state(vistos)

if __name__ == "__main__":
    main()
