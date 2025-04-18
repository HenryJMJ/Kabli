from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import time

usuarios = [
    {"usuario": "Administrador", "clave": "Admin@321"},
    {"usuario": "Docente", "clave": "docente1"},
    {"usuario": "Henry", "clave": "Henry1"}
]

CHROMEDRIVER_PATH = "C:/Users/LENOVO/OneDrive/Documentos/webdriver/chromedriver.exe"

drivers = []  # Para guardar los drivers y evitar que se cierren

for user in usuarios:
    options = webdriver.ChromeOptions()
    options.add_argument(f"--user-data-dir=C:/temp/selenium_profile_{user['usuario']}")  
    driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=options)
    drivers.append(driver)  # Guardamos el driver para que no se cierre automáticamente

    driver.get("http://127.0.0.1:8000/login/")

    time.sleep(2)

    driver.find_element(By.NAME, "username").send_keys(user["usuario"])
    driver.find_element(By.NAME, "password").send_keys(user["clave"])
    driver.find_element(By.TAG_NAME, "form").submit()

    time.sleep(2)

# 🚨 Espera hasta que tú decidas cerrar manualmente
input("Las sesiones están abiertas. Presiona Enter cuando quieras cerrar todo...")

# Cierre opcional (por si quieres limpiar después):
for driver in drivers:
    driver.quit()
