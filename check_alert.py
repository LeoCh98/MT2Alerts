import logging
import os
import time
import smtplib
from email.mime.text import MIMEText

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Environment variables (expected to be provided in GitHub Actions secrets)
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO")

def send_email(message):
    if not (EMAIL_ADDRESS and EMAIL_PASSWORD and EMAIL_TO):
        logger.error("Email credentials or recipient missing. Skipping send_email.")
        return False

    msg = MIMEText(message)
    msg['Subject'] = "MT2 Alert Notification"
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_TO

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
        logger.info("Email sent successfully to %s", EMAIL_TO)
        return True
    except Exception as e:
        logger.exception("Failed to send email: %s", e)
        return False


def check_page():
    # validate env early so we avoid starting the browser when configuration is missing
    if not (EMAIL_ADDRESS and EMAIL_PASSWORD and EMAIL_TO):
        logger.error("Required environment variables EMAIL_ADDRESS, EMAIL_PASSWORD or EMAIL_TO are not set.\n"
                     "Please add them as secrets in GitHub (Settings -> Secrets) or export them locally before running.")
        raise SystemExit(1)

    # Configure headless browser
    options = Options()
    # Use the new headless mode when supported, fallback to legacy if needed
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    # Try to detect a Chrome/Chromium binary on the system (GitHub runners commonly have /usr/bin/chromium)
    chrome_paths = [
        os.environ.get("CHROME_BIN"),
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
    ]
    for p in chrome_paths:
        if p and os.path.exists(p):
            logger.info("Found Chrome binary at %s", p)
            options.binary_location = p
            break

    logger.info("Starting Chrome WebDriver")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
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
            logger.info(message)
            success = send_email(message)
            if not success:
                logger.error("send_email reported failure. Check SMTP settings and credentials.")
        else:
            logger.info("No alerts found in this check.")
        return True
    finally:
        logger.info("Quitting WebDriver")
        try:
            driver.quit()
        except Exception:
            pass

if __name__ == "__main__":
    try:
        check_page()
    except SystemExit:
        # already logged helpful error message
        raise
    except Exception as e:
        logger.exception("Unhandled error while running check_page: %s", e)