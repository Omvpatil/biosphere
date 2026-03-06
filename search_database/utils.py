import os
from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
import polars as pl


def save_file(file: InMemoryUploadedFile) -> str:
    """
    Saves the uploadedfile to the MEDIA folder
    """
    file_path = os.path.join(settings.MEDIA_ROOT, file.name)
    with open(file_path, "wb+") as destination:
        for chunk in file.chunks():
            destination.write(chunk)
    return file_path


def read_csv_file(file_path: str) -> pl.DataFrame:
    data_df = pl.read_csv(file_path)
    return data_df


def add_research_papers_to_database(df: pl.DataFrame):
    data = df["Link"]
    for link in data:
        print(link)
