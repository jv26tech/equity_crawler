import unittest
from unittest.mock import MagicMock, patch, mock_open
from scraper import YahooEquityCrawler


class TestYahooEquityCrawler(unittest.TestCase):

    def setUp(self):
        # Mock do WebDriver para evitar abrir o navegador real
        with patch('scraper.webdriver.Chrome') as MockDriver:
            self.mock_driver = MockDriver.return_value
            self.crawler = YahooEquityCrawler("Argentina")
            self.crawler.driver = self.mock_driver

    def test_initialization(self):
        """Testa se a região é atribuída corretamente."""
        self.assertEqual(self.crawler.region, "Argentina")
        self.assertEqual(self.crawler.data, [])

    @patch('scraper.BeautifulSoup')
    def test_extract_data(self, mock_bs):
        """Testa a extração de dados com HTML simulado (Mock)."""
        # HTML Simulado contendo uma linha de tabela
        html_content = """
        <table>
            <tbody>
                <tr>
                    <td>AMX.BA</td>
                    <td>América Móvil, S.A.B. de C.V.</td>
                    <td>2089.00</td>
                </tr>
            </tbody>
        </table>
        """
        # Configura o mock do driver para retornar esse HTML
        self.crawler.driver.page_source = html_content

        # Configura o mock do BeautifulSoup para parsear o HTML simulado
        # Nota: Como o scraper instancia BS4 internamente, o patch deve ser na classe real ou
        # refatoramos para injetar o HTML. Aqui, vamos simular o comportamento do BS4 real:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        mock_bs.return_value = soup

        self.crawler._extract_data_from_page()

        # Verificações
        self.assertEqual(len(self.crawler.data), 1)
        self.assertEqual(self.crawler.data[0]['symbol'], 'AMX.BA')
        self.assertEqual(self.crawler.data[0]['price'], '2089.00')

    def test_save_to_csv(self):
        """Testa se a função de salvar tenta escrever no arquivo."""
        self.crawler.data = [{"symbol": "TEST", "name": "Test Co", "price": "100.00"}]

        with patch("builtins.open", mock_open()) as mock_file:
            self.crawler.save_to_csv()
            mock_file.assert_called_with("stocks_argentina.csv", 'w', newline='', encoding='utf-8')


if __name__ == '__main__':
    unittest.main()