from bs4 import BeautifulSoup
import requests


def fetch_paper_soup(pmcid: str) -> BeautifulSoup:
    """Fetches the XML once and creates the parser object."""
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={pmcid}&retmode=xml"

    response = requests.get(url)
    return BeautifulSoup(response.content, "xml")
