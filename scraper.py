import csv
import time
import logging
from typing import List, Dict
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class YahooEquityCrawler:
    """
    Crawler para extrair dados do Yahoo Finance filtrando por região.
    """

    BASE_URL = "https://finance.yahoo.com/research-hub/screener/equity/"

    def __init__(self, region: str):
        self.region = region
        self.data: List[Dict[str, str]] = []
        self.driver = self._setup_driver()

    @staticmethod
    def _setup_driver() -> webdriver.Chrome:
        options = Options()
        # options.add_argument("--headless")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")

        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)

    def _apply_region_filter(self):
        logging.info(f"Navegando para {self.BASE_URL}...")
        self.driver.get(self.BASE_URL)

        wait = WebDriverWait(self.driver, 20)

        try:
            region_container_xpath = "//div[contains(@class, 'menuContainer') and .//div[text()='Region']]"

            region_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, f"{region_container_xpath}//button")
            ))
            self.driver.execute_script("arguments[0].click();", region_btn)

            modal_xpath = f"{region_container_xpath}//div[contains(@class, 'menu-surface-dialog')]"
            modal = wait.until(EC.visibility_of_element_located((By.XPATH, modal_xpath)))

            try:
                us_label = modal.find_element(By.XPATH, ".//label[@title='United States']")
                us_input = us_label.find_element(By.TAG_NAME, "input")

                if us_input.is_selected():
                    us_label.click()
                    time.sleep(0.5)

            except Exception as e:
                logging.warning(f"Aviso ao desmarcar United States: {e}")

            search_input = modal.find_element(By.XPATH, ".//input[@placeholder='Search...']")
            search_input.clear()
            search_input.send_keys(self.region)

            time.sleep(1.5)

            target_checkbox = modal.find_element(By.XPATH, f".//label[@title='{self.region}']")
            target_checkbox.click()

            apply_btn = modal.find_element(By.XPATH, ".//button[@aria-label='Apply']")
            self.driver.execute_script("arguments[0].click();", apply_btn)

            wait.until(EC.invisibility_of_element_located((By.XPATH, modal_xpath)))

            time.sleep(3)
            logging.info("Filtro aplicado com sucesso.")

        except Exception as e:
            logging.error(f"Erro ao aplicar filtro: {e}")
            self.driver.save_screenshot("erro_region.png")
            raise

    def _extract_data_from_page(self):
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        rows = soup.select('table tbody tr')

        logging.info(f"Linhas encontradas: {len(rows)}")

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 3:
                continue

            try:
                symbol = cols[1].get_text(strip=True)
                name = cols[2].get_text(strip=True)
                price = cols[4].get_text(strip=True)

                self.data.append({
                    "symbol": symbol,
                    "name": name,
                    "price": price
                })
            except IndexError:
                continue

    def run(self):
        try:
            self._apply_region_filter()
            self._set_rows_to_100()

            page_count = 1
            while True:
                logging.info(f"Processando página {page_count}...")
                self._extract_data_from_page()

                if not self._go_to_next_page():
                    break

                page_count += 1

            self.save_to_csv()

        finally:
            self.driver.quit()

    def _go_to_next_page(self) -> bool:
        try:
            wait = WebDriverWait(self.driver, 10)
            next_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[data-testid="next-page-button"]')

            if next_btn.get_attribute("disabled") is not None:
                return False

            try:
                first_row_old = self.driver.find_element(By.CSS_SELECTOR,
                                                         'tr.row [data-testid-cell="ticker"] span.symbol').text
            except Exception as e:
                logging.error(f"Erro ao passar de página: {e}")
                first_row_old = ""

            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
            self.driver.execute_script("arguments[0].click();", next_btn)

            try:
                wait.until(lambda driver: driver.find_element(By.CSS_SELECTOR,
                                                              'tr.row [data-testid-cell="ticker"] span.symbol').text != first_row_old)
            except Exception:
                time.sleep(2)

            return True

        except Exception:
            return False

    def _set_rows_to_100(self):
        try:
            wait = WebDriverWait(self.driver, 10)

            pagination_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//div[contains(@class, 'paginationContainer')]//button[contains(@class, 'menuBtn')]")
            ))

            if "100" in pagination_btn.text:
                return

            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", pagination_btn)
            self.driver.execute_script("arguments[0].click();", pagination_btn)

            dropdown_menu = wait.until(EC.visibility_of_element_located(
                (By.CSS_SELECTOR, "div.dialog-container[aria-hidden='false']")
            ))

            option_100 = dropdown_menu.find_element(By.CSS_SELECTOR, 'div[data-value="100"]')
            self.driver.execute_script("arguments[0].click();", option_100)

            time.sleep(3)

        except Exception as e:
            logging.warning(f"Falha ao definir 100 linhas: {e}")

    def save_to_csv(self):
        filename = f"outputs/stocks_{self.region.replace(' ', '_').lower()}.csv"

        if not self.data:
            logging.warning("Sem dados para salvar.")
            return

        keys = ["symbol", "name", "price"]
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as output_file:
                dict_writer = csv.DictWriter(output_file, fieldnames=keys, quoting=csv.QUOTE_ALL)
                dict_writer.writeheader()
                dict_writer.writerows(self.data)
            logging.info(f"Arquivo salvo: {filename}")
        except IOError as e:
            logging.error(f"Erro de I/O: {e}")


if __name__ == "__main__":
    crawler = YahooEquityCrawler(region="Spain")
    crawler.run()