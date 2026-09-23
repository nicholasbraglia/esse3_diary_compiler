import os
import datetime
import logging
import time
import traceback
import pyotp
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
# from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

logger = logging.getLogger(__name__)

ESSE3_URL = "https://www.esse3.unimore.it/"

DAYS_ESSE3 = ['Lun.', 'Mar.', 'Mer.', 'Gio.', 'Ven.', 'Sab.', 'Dom.']

def execute_diary_sync(matrice_esse3, username, password, otp_seed):
    driver = None

    try:
        # Configure Chrome options
        chrome_options = Options()
        headless = os.getenv("SELENIUM_HEADLESS", "false").lower() in ("true", "1", "yes")
        if headless:
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")

        # Initialize driver (supporta Selenium standalone/remoto oppure Chrome locale)
        remote_url = os.getenv("SELENIUM_REMOTE_URL")
        if remote_url:
            logger.info(f"Connessione a Selenium remoto presso: {remote_url}")
            driver = webdriver.Remote(command_executor=remote_url, options=chrome_options)
        else:
            service = Service()
            driver = webdriver.Chrome(service=service, options=chrome_options)

        wait = WebDriverWait(driver, 10)

        logger.info(f"Avvio sincronizzazione Diario Docente per {len(matrice_esse3)} giornate")

        # Execute the table compiling process
        result = _execute_diary_navigation(
            driver=driver,
            wait=wait,
            matrice_esse3=matrice_esse3,
            username=username,
            password=password,
            otp_seed=otp_seed
        )

        return result

    except Exception as e:
        logger.error(f"Errore imprevisto nell'inizializzazione: {e}")
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'message': 'Impossibile avviare il processo automatico. Verificare i log.',
            'errors': [str(e)]
        }

    finally:
        if driver:
            try:
                driver.quit()
                logger.info("Driver del browser chiuso correttamente")
            except Exception as e:
                logger.warning(f"Errore nella chiusura del driver: {e}")


def _execute_diary_navigation(driver, wait, matrice_esse3, username, password, otp_seed):

    try:
        # Phase 1: Initial login and navigation
        logger.info("Fase 1: Avvio del processo di login")
        login_result = _handle_login_process(driver, wait, username, password, otp_seed)
        if not login_result['success']:
            return login_result

        # Phase 2: Navigate to diary
        logger.info("Fase 2: Navigazione alla sezione Diario Docente")
        nav_result = _navigate_to_diary(driver, wait)
        if not nav_result['success']:
            return nav_result

        # Phase 3: diary table compiling
        logger.info("Fase 3: Inserimento delle ore elaborate da Google Calendar")
        sync_result = _fill_diary_hours(driver, wait, matrice_esse3)

        return sync_result

    except Exception as e:
        logger.error(f"Errore durante la navigazione in Esse3: {e}")
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'message': 'Errore durante la navigazione nel sistema Esse3.',
            'errors': [str(e)]
        }


def _handle_login_process(driver, wait, username, password, otp_seed):
    """Handle the complete login process including OTP"""
    try:
        # Navigate to Esse3
        driver.get(ESSE3_URL)

        # Accept cookies
        try:
            cookies_ok = wait.until(
                EC.element_to_be_clickable((By.ID, "c-p-bn")))
            cookies_ok.click()
            logger.info("Cookie accettati")
        except TimeoutException:
            logger.warning("Pulsante cookie non trovato, proseguo...")

        # # Click access button
        # access_button = wait.until(EC.element_to_be_clickable((By.ID, "gu-toolBarLogin")))
        # access_button.click()

        menu = wait.until(EC.element_to_be_clickable((By.ID, "hamburger")))
        menu.click()

        login_from_menu = wait.until(EC.element_to_be_clickable((By.ID, "menu_link-navbox_account_LoginInfo")))
        login_from_menu.click()

        login_from_page = wait.until(EC.element_to_be_clickable((By.ID, "gu-toolBarLogin")))
        login_from_page.click()

        # Fill login form
        login_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//form//button[@type='submit' and @name='_eventId_proceed']")))
        driver.find_element(By.ID, "username").send_keys(username)
        driver.find_element(By.ID, "password").send_keys(password)
        login_button.click()

        logger.info("Credenziali di login inviate")

        # Handle OTP
        try:
            otp_field = wait.until(EC.element_to_be_clickable((By.ID, "tokencode")))
            totp = pyotp.TOTP(otp_seed)
            current_otp = totp.now()
            otp_field.send_keys(current_otp)

            otp_button = wait.until(EC.element_to_be_clickable((By.NAME, "_eventId_proceed")))
            otp_button.click()

            logger.info("Codice OTP inviato con successo")

        except TimeoutException:
            logger.error("Campo OTP non trovato - possibile fallimento del login")
            return {
                'success': False,
                'message': 'Errore durante il login: le credenziali inserite non sono valide o c\'è un problema di connessione al sistema Esse3',
                'processed_count': 0,
                'errors': ['Login fallito - verifica username e password']
            }

        # Select teacher profile
        try:
            submit_button = wait.until(EC.element_to_be_clickable((By.ID, "btnSceltaProfilo_7")))
            submit_button.click()
            logger.info("Profilo docente selezionato")
        except TimeoutException:
            logger.error("Selezione del profilo docente fallita")
            return {
                'success': False,
                'message': 'Errore nella selezione del profilo docente: verifica che il tuo account abbia i permessi necessari per accedere alle funzioni di verbalizzazione',
                'processed_count': 0,
                'errors': ['Selezione profilo docente fallita']
            }

        return {'success': True}

    except TimeoutException as e:
        logger.error(f"Timeout durante il processo di login: {e}")
        return {
            'success': False,
            'message': 'Timeout durante il processo di login: il sistema Esse3 non risponde o la connessione internet è lenta. Riprova più tardi.',
            'processed_count': 0,
            'errors': [f'Timeout login: {str(e)}']
        }
    except Exception as e:
        logger.error(f"Errore durante il login: {e}")
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'message': f'Errore imprevisto durante il login: impossibile accedere al sistema Esse3',
            'processed_count': 0,
            'errors': [f'Errore login: {str(e)}']
        }


def _navigate_to_diary(driver, wait):
    """Navigate to diary compiling page"""
    try:
        # Open menu
        menu = wait.until(EC.element_to_be_clickable((By.ID, "hamburger")))
        menu.click()

        # Select Area Docente
        area_docente_link = wait.until(EC.element_to_be_clickable((By.ID, "menu_link-navbox_docenti_Area_Docente")))
        area_docente_link.click()

        diario = wait.until(EC.element_to_be_clickable(By.ID, "menu_link-navbox_docenti_auth/docente/RegistroDocente/HomeDiario"))
        diario.click()

        xpath_edit_diary = "//input[@value='Dettaglio delle attività già inserite']"

        edit_diary = wait.until(
            EC.element_to_be_clickable((By.XPATH, xpath_edit_diary))
        )

        edit_diary.click()

        return {'success': True}

    except TimeoutException as e:
        logger.error(f"Timeout durante la navigazione: {e}")
        return {
            'success': False,
            'message': 'Timeout durante la navigazione alle sessioni di laurea: il sistema Esse3 non risponde o alcuni elementi non sono caricati correttamente.',
            'processed_count': 0,
            'errors': [f'Timeout navigazione: {str(e)}']
        }
    except Exception as e:
        logger.error(f"Errore durante la navigazione: {e}")
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'message': f'Errore durante la navigazione nel menu di Esse3: impossibile raggiungere la sezione sessioni di laurea',
            'processed_count': 0,
            'errors': [f'Errore navigazione: {str(e)}']
        }


def _convert_decimal_to_hhmm(decimal_hours):
    """Converts a number such as 2.5 into the string “02:30”."""
    hours = int(decimal_hours)
    minutes = int(round((decimal_hours - hours) * 60))
    return f"{hours:02d}:{minutes:02d}"


def _fill_diary_hours(driver, wait, esse3_matrix):
    problematic_dates = set()
    try:
        for iso_date, categories in esse3_matrix.items():
            # Prepare the dates
            data_dt = datetime.strptime(iso_date, "%Y-%m-%d")
            formatted_date = data_dt.strftime("%d/%m/%Y")
            logger.info(f"Elaborazione data: {formatted_date}")

            # 1. Search for date on Esse3
            date_input = wait.until(EC.element_to_be_clickable((By.ID, "diario_doc-inputSelData")))
            date_input.clear()
            date_input.send_keys(formatted_date)

            go_button = driver.find_element(By.ID, "btnVaiData")
            go_button.click()
            # time.sleep(2)  # Attesa per il ricaricamento della tabella

            # 2. Finding the right column
            # Construction of the header string (e.g. ‘Gio. 20’ or ‘Mar 01’)
            giorno_it = DAYS_ESSE3[data_dt.weekday()]
            giorno_numero = data_dt.strftime("%d")
            header_target = f"{giorno_it} {giorno_numero}"

            col_index = -1
            # headers = driver.find_elements(By.XPATH, "//table[@id='diario_doc-tabellaOre']//thead[1]//th")
            headers_xpath = "//table[@id='diario_doc-tabellaOre']//thead[1]//th"
            headers = wait.until(EC.presence_of_all_elements_located((By.XPATH, headers_xpath)))

            for index, th in enumerate(headers, start=1):
                if header_target in (th.get_attribute('textContent') or ""):
                    col_index = index
                    break

            if col_index == -1:
                logger.error(f"Colonna per '{header_target}' non trovata nella tabella di Esse3.")
                problematic_dates.add(formatted_date)
                continue

            logger.info(f"Data {header_target} trovata in colonna {col_index}. Inizio compilazione...")

            # 3. Compiling
            for category, decimal_hours in categories.items():
                if decimal_hours > 0:
                    try:
                        xpath = f"//table[@id='diario_doc-tabellaOre']//tbody/tr[td[1][contains(normalize-space(text()), '{category}')]]/td[{col_index}]//input[@type='text']"
                        hour_cell = driver.find_element(By.XPATH, xpath)

                        formatted_hours = _convert_decimal_to_hhmm(decimal_hours)
                        hour_cell.clear()
                        hour_cell.send_keys(formatted_hours)
                        wait.until(lambda d: hour_cell.get_attribute("value") == formatted_hours)
                        logger.info(f"Inserite {formatted_hours} ore in '{category}'")
                        # time.sleep(0.5)

                    except Exception as e:
                        logger.warning(f"Impossibile inserire ore per {category}: {e}")
                        problematic_dates.add(formatted_date)

            # 4. Saving
            save_button = wait.until(EC.element_to_be_clickable((By.ID, "sbmDef")))
            save_button.click()
            # time.sleep(2)
            wait.until(EC.element_to_be_clickable((By.ID, "diario_doc-inputSelData")))

            logger.info("Salvataggio confermato per la giornata.")

        if problematic_dates:
            dates_str = ", ".join(sorted(list(problematic_dates)))
            return {
                'success': True, 
                'message': f'Sincronizzazione completata con eccezioni. Le seguenti date hanno avuto problemi (nessuna colonna/riga trovata): {dates_str}'
            }
        else:
            return {'success': True, 'message': 'Sincronizzazione Diario completata!'}

    except Exception as e:
        logger.error(f"Errore durante l'inserimento ore: {e}")
        return {'success': False, 'message': 'Errore', 'errors': [str(e)]}