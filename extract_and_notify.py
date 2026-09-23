import os
import json
import time
import requests
import subprocess
import UnityPy
from io import BytesIO

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
STATE_FILE = "vistos.json"
RUST_DIR = "rust_staging"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return set(json.load(f))
        except json.JSONDecodeError:
            return set()
    return set()

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(list(state), f)

def render_3d_to_png(obj_bytes, name):
    """Guarda el OBJ temporalmente y ejecuta Blender para sacar la captura PNG"""
    obj_path = f"/tmp/{name}.obj"
    png_path = f"/tmp/{name}.png"
    
    with open(obj_path, "wb") as f:
        f.write(obj_bytes)
        
    # Ejecuta Blender de forma transparente sin interfaz
    subprocess.run([
        "blender", "-b", "--python", "render_3d.py", "--", obj_path, png_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if os.path.exists(png_path):
        with open(png_path, "rb") as f:
            rendered_bytes = f.read()
        os.remove(obj_path)
        os.remove(png_path)
        return rendered_bytes
    return None

def send_to_discord(name, asset_type, file_bytes=None):
    payload = {
        "embeds": [{
            "title": f"🆕 Nuevo Asset Detectado: `{name}`",
            "footer": {"text": "Rust Staging Dataminer • GitHub Actions"}
        }]
    }
    
    files = None

    if asset_type == "AudioClip":
        payload["embeds"][0]["description"] = "🔊 Nuevo audio detectado. Escúchalo abajo:"
        payload["embeds"][0]["color"] = 15844367
        if file_bytes:
            files = {"file": (f"{name}.wav", file_bytes, "audio/wav")}
            
    elif asset_type in ["Texture2D", "Sprite"]:
        payload["embeds"][0]["description"] = "🖼️ Nueva imagen/textura 2D detectada:"
        payload["embeds"][0]["color"] = 8302335
        if file_bytes:
            files = {"file": (f"{name}.png", file_bytes, "image/png")}
            payload["embeds"][0]["thumbnail"] = {"url": f"attachment://{name}.png"}
            
    elif asset_type in ["GameObject", "Mesh"]:
        payload["embeds"][0]["description"] = "📦 Nuevo modelo 3D detectado (Renderizado 2D):"
        payload["embeds"][0]["color"] = 3447003
        if file_bytes:
            files = {"file": (f"{name}.png", file_bytes, "image/png")}
            payload["embeds"][0]["thumbnail"] = {"url": f"attachment://{name}.png"}

    response = requests.post(WEBHOOK_URL, data={"payload_json": json.dumps(payload)}, files=files)
    print(f"Enviado {name}: {response.status_code}")

def main():
    if not WEBHOOK_URL:
        return

    vistos = load_state()
    is_first_run = len(vistos) == 0

    archivos_unity = []
    for root, dirs, files in os.walk(RUST_DIR):
        for file in files:
            if file.endswith(".bundle") or file.endswith(".assets"):
                archivos_unity.append(os.path.join(root, file))

    env = UnityPy.load(*archivos_unity)
    nuevos_encontrados = 0

    for obj in env.objects:
        if obj.type.name in ["Texture2D", "Sprite", "GameObject", "Mesh", "AudioClip"]:
            data = obj.read()
            name = getattr(data, "name", getattr(data, "m_Name", None))
            if not name:
                continue

            is_icon = obj.type.name in ["Texture2D", "Sprite"] and ("icon" in name.lower() or "item" in name.lower())
            is_3d = obj.type.name in ["GameObject", "Mesh"] and any(k in name.lower() for k in ["npc", "animal", "monument", "vehicle", "weapon"])
            is_audio = obj.type.name == "AudioClip" and any(k in name.lower() for k in ["sound", "audio", "weapon", "fx", "music", "vo", "ambient"])

            if (is_icon or is_3d or is_audio) and name not in vistos:
                if is_first_run:
                    vistos.add(name)
                else:
                    try:
                        if is_icon:
                            img_byte_arr = BytesIO()
                            data.image.save(img_byte_arr, format='PNG')
                            send_to_discord(name, obj.type.name, img_byte_arr.getvalue())
                        elif is_audio:
                            audio_bytes = next(iter(data.samples.values()), None) if hasattr(data, "samples") else None
                            send_to_discord(name, obj.type.name, audio_bytes)
                        elif is_3d:
                            png_render = None
                            if obj.type.name == "Mesh" and hasattr(data, "export"):
                                obj_bytes = data.export().encode('utf-8')
                                png_render = render_3d_to_png(obj_bytes, name)
                            send_to_discord(name, obj.type.name, png_render)

                        vistos.add(name)
                        nuevos_encontrados += 1
                    except Exception as e:
                        print(f"Error procesando {name}: {e}")

                    if nuevos_encontrados >= 10:
                        save_state(vistos)
                        time.sleep(60)
                        nuevos_encontrados = 0

    save_state(vistos)

if __name__ == "__main__":
    main()
