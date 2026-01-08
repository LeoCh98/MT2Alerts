import logging
import os
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging..
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Environment variables..
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO")

# Price threshold..
PRICE_THRESHOLD = 1000

def send_email(message, html_message=None):
    if not (EMAIL_ADDRESS and EMAIL_PASSWORD and EMAIL_TO):
        logger.error("Email credentials or recipient missing. Skipping send_email.")
        return False

    msg = MIMEMultipart("alternative")
    msg['Subject'] = "MT2 Alert Notification"
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_TO

    # Attach plain text
    part1 = MIMEText(message, "plain")
    msg.attach(part1)
    # Attach HTML if provided
    if html_message:
        part2 = MIMEText(html_message, "html")
        msg.attach(part2)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
        return True
    except Exception as e:
        logger.exception("Failed to send email: %s", e)
        return False


def check_page():
    # Validate env config..
    if not (EMAIL_ADDRESS and EMAIL_PASSWORD and EMAIL_TO):
        logger.error("Required environment variables EMAIL_ADDRESS, EMAIL_PASSWORD or EMAIL_TO are not set.\n"
                     "Please add them as secrets in GitHub (Settings -> Secrets) or export them locally before running.")
        raise SystemExit(1)

    # Configure headless browser..
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    # Try to detect a Chrome/Chromium binary on the system..
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

    # If a remote Selenium server is provided, use it. (Not set in this version..)
    remote_url = os.getenv("SELENIUM_REMOTE_URL")
    if remote_url:
        logger.info("Using remote Selenium server at %s", remote_url)
        # webdriver.Remote will talk to the provided Selenium standalone container
        driver = webdriver.Remote(command_executor=remote_url, options=options)
    else:
        logger.info("Starting local Chrome WebDriver")
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

        # === Step 4: Iterate over first items (expand to first 10 by default) ===
        rows = driver.find_elements(By.XPATH, "//table//tr")[:10]
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
                    # Seller/vendedor (column 6)
                    try:
                        vendedor_element = row.find_element(By.XPATH, ".//td[6]")
                        vendedor = vendedor_element.text.strip()
                    except Exception:
                        vendedor = "(unknown)"

                    # Print/log the comparison so we can debug why an item triggers or not
                    is_alert = precio <= PRICE_THRESHOLD
                    # Trigger alert if price is less than or equal to threshold
                    if is_alert:
                        found_alerts.append((nombre_completo, precio, vendedor))
            except Exception:
                continue

        # === Step 5: Send email if any alert found ===
        if found_alerts:
            message = "Found items with low price:\n\n" + "\n".join(
                f"(Item: {nombre}) ({precio} Yang) — Vendedor: {vendedor}" for nombre, precio, vendedor in found_alerts
            )
            html_alerts = []
            for nombre, precio, vendedor in found_alerts:
                html_alerts.append(
                    f"<p>(Item: <b>{nombre}</b>) (<b>{precio}</b> Yang) — Vendedor: <b>{vendedor}</b></p>"
                )
            html_message = "<html><body><h2>Found items with low price:</h2>" + "".join(html_alerts) + "</body></html>"
            success = send_email(message, html_message)
            if not success:
                logger.error("send_email reported failure. Check SMTP settings and credentials.")
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
        logger.exception("Unhandled error while running: %s", e)