from typing import Any, Dict

from bs4 import BeautifulSoup
from django.core.files.base import ContentFile

from search_database.models import ImageNodes, ResearchPaper

import requests
import logging

logger = logging.getLogger(__name__)


def download_and_save_image(pmcid: str, fig_id: str, caption_text: str):
    """
    Downloads the actual JPG from NCBI and saves it directly to the Django database.
    """
    figure_page_url = (
        f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/figure/{fig_id}/"
    )

    try:
        # 1. Fetch the HTML to find today's CDN hash
        html_response = requests.get(figure_page_url, timeout=10)
        soup = BeautifulSoup(html_response.content, "html.parser")

        img_tag = soup.find("img", class_="graphic")
        if img_tag and img_tag.get("src"):
            cdn_url = img_tag.get("src")

            # 2. Download the actual binary JPG data
            image_response = requests.get(cdn_url, timeout=10)

            if image_response.status_code == 200:
                new_image = ImageNodes(
                    pmcid=pmcid, link=figure_page_url, description=caption_text
                )

                file_name = f"{pmcid}_{fig_id}.jpg"
                new_image.image_file.save(
                    file_name, ContentFile(image_response.content), save=True
                )

                logger.info(f"Successfully downloaded and saved {file_name}")
                return new_image

    except Exception as e:
        logger.error(f"Failed to download image {fig_id} for {pmcid}: {e}")
        return None


def store_images(paper_instance: ResearchPaper, data: Dict[str, Any]):
    logger.info(f"Storing Images for {data['pmcid']}")
    for image_data in data["images"]:
        image_obj = download_and_save_image(
            pmcid=data["pmcid"],
            fig_id=image_data["fig_id"],
            caption_text=image_data["description"],
        )
        if image_obj:
            paper_instance.images.add(image_obj)
            logger.info(f"Stored Images for {data['pmcid']}")
