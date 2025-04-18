import requests
import json
import subprocess

# Ruta a tu archivo capacitor.config.json
CAPACITOR_CONFIG_PATH = "C:/plataforma-educativa/capacitor.config.json"

def obtener_url_ngrok():
    """Obtiene la URL pública de ngrok"""
    try:
        # Obtén los túneles desde la API de ngrok
        res = requests.get("http://127.0.0.1:4040/api/tunnels")
        data = res.json()
        
        # Busca el túnel con protocolo HTTPS
        for tunnel in data["tunnels"]:
            if tunnel["proto"] == "https":
                return tunnel["public_url"]
    except Exception as e:
        print(f"Error al obtener URL de ngrok: {e}")
    return None

def actualizar_capacitor_config(nueva_url):
    """Actualiza el archivo capacitor.config.json con la nueva URL"""
    with open(CAPACITOR_CONFIG_PATH, "r") as f:
        config = json.load(f)

    if "server" not in config:
        config["server"] = {}

    # Actualiza la URL de ngrok
    config["server"]["url"] = nueva_url
    config["server"]["cleartext"] = True

    # Guarda el archivo actualizado
    with open(CAPACITOR_CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

    print(f"capacitor.config.json actualizado con la URL: {nueva_url}")

def sync_android():
    """Sincroniza los cambios con el proyecto Android"""
    subprocess.run(["npx", "cap", "sync", "android"], shell=True)

if __name__ == "__main__":
    # Obtener la URL de ngrok
    url_ngrok = obtener_url_ngrok()
    if url_ngrok:
        # Actualizar capacitor.config.json con la nueva URL
        actualizar_capacitor_config(url_ngrok)
        # Sincronizar los cambios con Android
        sync_android()
    else:
        print("No se pudo obtener la URL de ngrok.")
