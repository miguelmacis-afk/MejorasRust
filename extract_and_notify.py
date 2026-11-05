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
SKINS_OUTPUT_FILE = "BuildingSkins.cs"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except (json.JSONDecodeError, ValueError):
            return set()
    return set()

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(state), f)

def load_existing_skins_data():
    # Estructura inicial con los grados de construcción de Rust por defecto
    skins = {
        1: {"NORMAL": 0, "LEGACY": 10232, "Gingerbread": 2},
        2: {"NORMAL": 0, "ADOBE": 10220, "BRICK": 10223, "BRUTALIST": 10225, "JUNGLE": 10326, "CRYPT": 10472},
        3: {"NORMAL": 0, "CONTAINER": 10240, "SCRAPKING": 10242},
        4: {"NORMAL": 0, "SPACE": 10430}
    }
    return skins

def save_skins_to_csharp(skins_dict):
    """Genera y actualiza automáticamente el archivo C# con el formato de diccionario"""
    lines = [
        "using System.Collections.Generic;",
        "",
        "namespace RustBuildingSkins",
        "{",
        "    public class BuildingSkinData",
        "    {",
        "        private const ulong SKIN_CONTAINER = 10240;",
        "",
        "        private readonly Dictionary<int, Dictionary<string, ulong>> SkinsDisponibles = new Dictionary<int, Dictionary<string, ulong>>",
        "        {"
    ]
    
    grade_keys = sorted(skins_dict.keys())
    for idx, grade in enumerate(grade_keys):
        inner_items = []
        for s_name, s_id in skins_dict[grade].items():
            if s_name == "CONTAINER" and s_id == 10240:
                inner_items.append('{"CONTAINER", SKIN_CONTAINER}')
            else:
                inner_items.append(f'{{"{s_name}", {s_id}}}')
        
        inner_str = ", ".join(inner_items)
        comma = "," if idx < len(grade_keys) - 1 else ""
        lines.append(f"            {{ {grade}, new Dictionary<string, ulong> {{ {inner_str} }} }}{comma}")
        
    lines.extend([
        "        };",
        "    }",
        "}"
    ])
    
    with open(SKINS_OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Archivo {SKINS_OUTPUT_FILE} actualizado automáticamente.")

def render_3d_to_png(obj_bytes, name):
    obj_path = f"/tmp/{name}.obj"
    png_path = f"/tmp/{name}.png"
    try:
        with open(obj_path, "wb") as f:
            f.write(obj_bytes)
        subprocess.run([
            "blender", "-b", "--python", "render_3d.py", "--", obj_path, png_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(png_path):
            with open(png_path, "rb") as f:
                return f.read()
    except Exception as e:
        print(f"Error en render_3d_to_png para {name}: {e}")
    finally:
        if os.path.exists(obj_path):
            os.remove(obj_path)
        if os.path.exists(png_path):
            os.remove(png_path)
    return None

def send_to_discord(name, asset_type, file_bytes=None):
    if not WEBHOOK_URL:
        return
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

    try:
        response = requests.post(WEBHOOK_URL, data={"payload_json": json.dumps(payload)}, files=files)
        print(f"Enviado {name}: {response.status_code}")
    except Exception as e:
        print(f"Error enviando a Discord ({name}): {e}")

def main():
    vistos = load_state()
    skins_dict = load_existing_skins_data()
    is_first_run = len(vistos) == 0

    if not os.path.exists(RUST_DIR):
        print(f"El directorio {RUST_DIR} no existe.")
        return

    archivos_unity = []
    for root, dirs, files in os.walk(RUST_DIR):
        for file in files:
            if file.endswith((".bundle", ".assets", ".resource")):
                archivos_unity.append(os.path.join(root, file))

    if not archivos_unity:
        print("No se encontraron archivos de Unity para procesar.")
        return

    print(f"Cargando {len(archivos_unity)} archivos de Unity...")
    env = UnityPy.load(*archivos_unity)
    nuevos_encontrados = 0

    for obj in env.objects:
        if obj.type.name in ["Texture2D", "Sprite", "GameObject", "Mesh", "AudioClip", "MonoBehaviour"]:
            try:
                data = obj.read()
                name = getattr(data, "name", getattr(data, "m_Name", None))
                if not name:
                    continue

                lower_name = name.lower()

                # NOTA: Aquí puedes mapear la lógica de extracción si descubres propiedades 
                # de skin de construcción específicas en los assets analizados de Rust:
                # Ejemplo:
                # if "nueva_skin_construccion" in lower_name:
                #     skins_dict[grado][nombre_skin] = id_skin
                #     skins_actualizadas = True

                is_icon = obj.type.name in ["Texture2D", "Sprite"] and any(k in lower_name for k in ["icon", "item", "skin"])
                is_3d = obj.type.name in ["GameObject", "Mesh"] and any(k in lower_name for k in ["npc", "animal", "monument", "vehicle", "weapon"])
                is_audio = obj.type.name == "AudioClip" and any(k in lower_name for k in ["sound", "audio", "weapon", "fx", "music", "vo", "ambient"])

                if (is_icon or is_3d or is_audio) and name not in vistos:
                    if is_first_run:
                        vistos.add(name)
                    else:
                        file_payload = None
                        if is_icon:
                            img_byte_arr = BytesIO()
                            if hasattr(data, "image") and data.image:
                                data.image.save(img_byte_arr, format='PNG')
                                file_payload = img_byte_arr.getvalue()
                        elif is_audio:
                            if hasattr(data, "samples") and data.samples:
                                file_payload = next(iter(data.samples.values()), None)
                            elif hasattr(data, "export"):
                                export_data = data.export()
                                if isinstance(export_data, bytes):
                                    file_payload = export_data
                        elif is_3d:
                            if obj.type.name == "Mesh" and hasattr(data, "export"):
                                exp = data.export()
                                if exp:
                                    obj_bytes = exp.encode('utf-8') if isinstance(exp, str) else exp
                                    file_payload = render_3d_to_png(obj_bytes, name)

                        send_to_discord(name, obj.type.name, file_payload)
                        vistos.add(name)
                        nuevos_encontrados += 1

                        if nuevos_encontrados >= 10:
                            save_state(vistos)
                            time.sleep(5)
                            nuevos_encontrados = 0

            except Exception as e:
                print(f"Error procesando objeto {obj.path_id}: {e}")

    save_state(vistos)
    save_skins_to_csharp(skins_dict)
    print("Datamining y guardado de skins completados.")

if __name__ == "__main__":
    main()
