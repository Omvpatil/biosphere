from django.http import response
from search_database.models import ResearchPaper
from search_database.serializers import CsvDataSerializer, ResearchPaperSerializer
from rest_framework.response import Response
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import generics, status
from search_database.utils import (
    add_research_papers_to_database,
    read_csv_file,
    save_file,
)


@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
def upload_csv(request):
    serializer = CsvDataSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"errors": serializer.errors})
    if not serializer.validated_data["file"].name.endswith(".csv"):
        return Response(
            {
                "message": "Only csv file accepted",
                "errors": status.HTTP_406_NOT_ACCEPTABLE,
            }
        )
    file_path = save_file(serializer.validated_data["file"])
    df = read_csv_file(file_path)
    add_research_papers_to_database(df)
    return Response(status=status.HTTP_200_OK)


class ResearchPaperListAPIView(generics.ListAPIView):
    queryset = ResearchPaper.objects.all()
    serializer_class = ResearchPaperSerializer


class ResearchPaperDetailAPIView(generics.RetrieveAPIView):
    queryset = ResearchPaper.objects.all()
    serializer_class = ResearchPaperSerializer
