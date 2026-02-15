import unittest
from unittest.mock import MagicMock, patch, mock_open
from scraper import YahooEquityCrawler


class TestYahooEquityCrawler(unittest.TestCase):

    def setUp(self):
        self.patcher = patch('scraper.webdriver.Chrome')
        self.MockDriver = self.patcher.start()
        self.mock_driver = self.MockDriver.return_value

        self.crawler = YahooEquityCrawler("Spain")
        self.crawler.driver = self.mock_driver

    def tearDown(self):
        self.patcher.stop()

    def test_initialization(self):
        self.assertEqual(self.crawler.region, "Spain")
        self.assertEqual(self.crawler.data, [])
        self.MockDriver.assert_called()

    def test_extract_data_success(self):
        html_content = """
        <html><body><table><tbody>
            <tr>
                <td>-</td><td>SAN.MC</td><td>Banco Santander</td><td>-</td><td>3.50</td><td>-</td>
            </tr>
            <tr>
                 <td>-</td><td>BBVA.MC</td><td>Banco Bilbao</td><td>-</td><td>7.20</td><td>-</td>
            </tr>
        </tbody></table></body></html>
        """
        self.mock_driver.page_source = html_content
        self.crawler._extract_data_from_page()

        self.assertEqual(len(self.crawler.data), 2)
        self.assertEqual(self.crawler.data[0]['symbol'], 'SAN.MC')
        self.assertEqual(self.crawler.data[0]['name'], 'Banco Santander')
        self.assertEqual(self.crawler.data[0]['price'], '3.50')

    def test_extract_data_incomplete_rows(self):
        self.mock_driver.page_source = "<table><tbody><tr><td>Bad Row</td><td>X</td></tr></tbody></table>"
        self.crawler._extract_data_from_page()
        self.assertEqual(len(self.crawler.data), 0)

    def test_go_to_next_page_success(self):
        mock_btn = MagicMock()
        mock_btn.get_attribute.return_value = None
        self.mock_driver.find_element.return_value = mock_btn

        self.assertTrue(self.crawler._go_to_next_page())
        self.mock_driver.execute_script.assert_any_call("arguments[0].click();", mock_btn)

    def test_go_to_next_page_disabled(self):
        mock_btn = MagicMock()
        mock_btn.get_attribute.return_value = "true"
        self.mock_driver.find_element.return_value = mock_btn

        self.assertFalse(self.crawler._go_to_next_page())
        self.mock_driver.execute_script.assert_not_called()

    @patch('scraper.WebDriverWait')
    def test_set_rows_to_100(self, MockWait):
        wait = MockWait.return_value

        mock_pag_btn = MagicMock()
        mock_pag_btn.text = "25"
        mock_dropdown = MagicMock()
        mock_option_100 = MagicMock()

        wait.until.side_effect = [mock_pag_btn, mock_dropdown]
        mock_dropdown.find_element.return_value = mock_option_100

        self.crawler._set_rows_to_100()

        self.assertTrue(self.mock_driver.execute_script.call_count >= 2)
        mock_dropdown.find_element.assert_called_with('css selector', 'div[data-value="100"]')

    @patch('scraper.WebDriverWait')
    def test_apply_region_filter(self, MockWait):
        wait = MockWait.return_value

        # Mocks para os elementos
        mock_region_btn = MagicMock()
        mock_modal = MagicMock()

        mock_us_label = MagicMock()
        mock_us_input = MagicMock()
        mock_search = MagicMock()
        mock_target = MagicMock()
        mock_apply = MagicMock()

        # Configuração: Simula que 'United States' está marcado (true)
        mock_us_input.is_selected.return_value = True
        mock_us_label.find_element.return_value = mock_us_input

        # Configuração: WebDriverWait
        # A ordem exata das chamadas no código é:
        # 1. Botão Region -> Retorna o botão
        # 2. Modal Visível -> Retorna o CONTAINER do modal (IMPORTANTE)
        # 3. Modal Invisível -> Retorna True/None
        wait.until.side_effect = [mock_region_btn, mock_modal, True]

        # Configuração: Busca dentro do Modal
        def modal_side_effect(by, value):
            val_str = str(value)
            if "United States" in val_str: return mock_us_label
            if "Search" in val_str: return mock_search
            if self.crawler.region in val_str: return mock_target
            if "Apply" in val_str: return mock_apply
            return MagicMock()

        mock_modal.find_element.side_effect = modal_side_effect

        # Execução
        self.crawler._apply_region_filter()

        # Asserts
        self.mock_driver.get.assert_called_with(self.crawler.BASE_URL)

        # Confirma clique no botão Region (via JS)
        self.mock_driver.execute_script.assert_any_call("arguments[0].click();", mock_region_btn)

        # Confirma lógica de desmarcar US
        mock_us_label.click.assert_called()

        # Confirma busca e seleção da região alvo
        mock_search.send_keys.assert_called_with("Spain")
        mock_target.click.assert_called()

        # Confirma clique no Apply
        self.mock_driver.execute_script.assert_any_call("arguments[0].click();", mock_apply)

    def test_run_flow(self):
        with patch.object(self.crawler, '_apply_region_filter') as mock_apply, \
                patch.object(self.crawler, '_set_rows_to_100') as mock_rows, \
                patch.object(self.crawler, '_extract_data_from_page') as mock_extract, \
                patch.object(self.crawler, '_go_to_next_page') as mock_next, \
                patch.object(self.crawler, 'save_to_csv') as mock_save:
            mock_next.side_effect = [True, False]

            self.crawler.run()

            mock_apply.assert_called_once()
            mock_rows.assert_called_once()
            self.assertEqual(mock_extract.call_count, 2)
            self.assertEqual(mock_next.call_count, 2)
            mock_save.assert_called_once()
            self.mock_driver.quit.assert_called_once()

    def test_save_to_csv_with_data(self):
        self.crawler.data = [
            {"symbol": "A", "name": "Co A", "price": "10"},
            {"symbol": "B", "name": "Co B", "price": "20"}
        ]
        with patch("builtins.open", mock_open()) as mock_file:
            self.crawler.save_to_csv()
            mock_file.assert_called_with("outputs/stocks_spain.csv", 'w', newline='', encoding='utf-8')
            self.assertTrue(mock_file().write.called)

    def test_save_to_csv_empty(self):
        self.crawler.data = []
        with patch("builtins.open", mock_open()) as mock_file:
            self.crawler.save_to_csv()
            mock_file.assert_not_called()


if __name__ == '__main__':
    unittest.main()