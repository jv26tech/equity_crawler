import sys
from scraper import YahooEquityCrawler


def main():
    # Permite passar a região via linha de comando ou usa 'Argentina' como padrão [cite: 6]
    region = sys.argv[1] if len(sys.argv) > 1 else "Argentina"

    print(f"Iniciando crawler para a região: {region}...")
    crawler = YahooEquityCrawler(region)
    crawler.run()


if __name__ == "__main__":
    main()