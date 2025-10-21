from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import smtplib
from email.mime.text import MIMEText
import os
import time

# Configure headless browser
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO")

def send_email(message):
    msg = MIMEText(message)
    msg['Subject'] = "MT2 Alert Notification"
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_TO

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

def check_page():
    driver.get("https://metin2alerts.com/store")

    wait = WebDriverWait(driver, 15)

    # === Step 1: Select Spanish Language ===
    bandera_es = wait.until(EC.element_to_be_clickable((By.XPATH, "//img[@src='country/es.png']")))
    bandera_es.click()
    time.sleep(2)

    # === Step 2: Select Iberia Server ===
    select_server = wait.until(EC.element_to_be_clickable((By.ID, "server-select")))
    select = Select(select_server)
    select.select_by_value("506")  # Iberia

    # === Step 3: Sort by "Price (Ascending)" ===
    select_sort = wait.until(EC.element_to_be_clickable((By.ID, "sort-by-select")))
    sort = Select(select_sort)
    sort.select_by_value("fiyat-artan")

    time.sleep(4)

    # === Step 4: Iterate over first 5 items ===
    rows = driver.find_elements(By.XPATH, "//table//tr")[:5]
    found_alerts = []

    for row in rows:
        try:
            # Item name
            nombre_element = row.find_element(By.XPATH, ".//td[2]//div[@class='font-medium text-white text-sm']")
            nombre = nombre_element.text.strip()

            # Bonus description
            try:
                descripcion_element = row.find_element(By.XPATH, ".//td[2]//span")
                descripcion = descripcion_element.text.strip()
                nombre_completo = f"{nombre} — {descripcion}"
            except:
                nombre_completo = nombre

            # Price..
            precio_element = row.find_element(By.XPATH, ".//td[4]")
            precio_texto = precio_element.text.strip().replace('.', '').replace(',', '')
            precio = int(precio_texto) if precio_texto.isdigit() else None

            if precio is not None:
                if precio < 1000:
                    found_alerts.append(f"{nombre_completo} ({precio} Yang)")
        except Exception:
            continue

    # === Step 5: Send email if any alert found ===
    if found_alerts:
        message = "Found items with low price:\n\n" + "\n".join(found_alerts)
        print(message)
        send_email(message)

if __name__ == "__main__":
    try:
        check_page()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()