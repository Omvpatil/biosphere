import json
import logging
import re
from typing import List
import pandas as pd

from search_database.workflows.ingestion import add_single_paper_to_database

logger = logging.getLogger(__name__)


def stream_research_papers_ingestion(df: pd.DataFrame) -> List:
    total_papers = len(df["Link"].tolist())
    for index, rp_link in enumerate(df["Link"]):
        pmcid = re.search(r"(PMC\d+)", rp_link).group(1)
        yield f"data: {json.dumps({'status': 'processing', 'pmcid': pmcid, 'progress': f'{index + 1}/{total_papers}'})}\n\n"
        try:
            success_msg = add_single_paper_to_database(pmcid)
            yield f"data: {json.dumps({'status': 'success', 'pmcid': pmcid, 'message': success_msg})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'pmcid': pmcid, 'message': str(e)})}\n\n"
    yield f"data: {json.dumps({'status': 'completed', 'message': 'All papers processed.'})}\n\n"
