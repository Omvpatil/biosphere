from django.core import signing
from django.http import FileResponse, Http404, StreamingHttpResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from search_database.models import ImageNodes, ResearchPaper
from search_database.search import extract_facets
from search_database.serializers import (
    CsvDataSerializer,
    DocumentChunksSerializer,
    FinalOutputSerializer,
    ResearchPaperSerializer,
    UserQuerySerializer,
)
from rest_framework.response import Response
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import generics, status
import pandas as pd

from search_database.ai import query_rewriter
from search_database.workflows.response_output import stream_llm_response
from search_database.workflows.streaming import stream_research_papers_ingestion


@csrf_exempt
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
    file_path = serializer.validated_data["file"]
    df = pd.read_csv(file_path)
    return StreamingHttpResponse(
        stream_research_papers_ingestion(df), content_type="text/event-stream"
    )


from biosphere.models import ChatSession, ChatMessage, ChatRole, User
import json

def sse_event_generator(user_query, chat_history, session=None):
    try:
        if session:
            # Yield the session id back to the frontend so it can pass it on subsequent follow-ups
            yield f"data: {json.dumps({'type': 'session_id', 'session_id': session.id})}\\n\\n"

        final_ai_text = ""
        for event in stream_llm_response(user_query, chat_history):
            if event.get("type") == "token":
                final_ai_text += event.get("content", "")
            yield f"data: {json.dumps(event)}\\n\\n"
            
        # Post-processing: Save ONLY the final AI text to avoid storing and re-feeding vast RAG chunks.
        if session and final_ai_text:
            ChatMessage.objects.create(
                session=session,
                role=ChatRole.ASSISTANT,
                content=final_ai_text
            )
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in sse_event_generator: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\\n\\n"

@api_view(["POST"])
def chat_search_stream_view(request):
    try:
        data = request.data
        user_query = data.get("user_query")
        session_id = data.get("session_id")
        
        if not user_query:
            return Response({"error": "user_query is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        # 1. Manage ChatSession
        session = None
        if session_id:
            try:
                session = ChatSession.objects.get(id=session_id)
            except ChatSession.DoesNotExist:
                return Response({"error": "Invalid session_id"}, status=status.HTTP_404_NOT_FOUND)
        else:
            user = request.user if request.user.is_authenticated else User.objects.first()
            if user:
                session = ChatSession.objects.create(user=user, title=user_query[:50])

        # 2. Build lean Chat History from DB
        chat_history = ""
        if session:
            # Build string from previous interactions. We explicitly DO NOT fetch or append the RAG contexts
            # to prevent the LLM context window from ballooning.
            for msg in session.messages.order_by("created_at"):
                role_label = "User" if msg.role == ChatRole.USER else "AI"
                chat_history += f"{role_label}: {msg.content}\\n"
                
            # Log current user message
            ChatMessage.objects.create(
                session=session,
                role=ChatRole.USER,
                content=user_query
            )
        else:
            # Fallback if no db user available
            chat_history = data.get("chat_history", "")
        
        response = StreamingHttpResponse(
            sse_event_generator(user_query, chat_history, session=session),
            content_type="text/event-stream"
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no' # For Nginx compatibility
        return response
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in chat_search_stream_view: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Kept for backward compatibility if needed, but updated to use the old return format via stream aggregation.
@api_view(["POST"])
def test_functions(request):
    query = UserQuerySerializer(data=request.data)
    query.is_valid(raise_exception=True)
    user_query = query.validated_data["user_query"]
    chat_history = query.validated_data.get("chat_history", "")
    
    events = list(stream_llm_response(user_query, chat_history))
    
    # Very rudimentary aggregation for non-streaming clients
    final_text = ""
    papers = []
    for evt in events:
        if evt.get("type") == "token":
            final_text += evt.get("content", "")
        if evt.get("type") == "data" and papers == []:
            papers = evt.get("papers", [])
            
    return Response(
        {
             "final_output": {
                 "answer": final_text,
                 "papers_context": papers
             }
        },
        status=status.HTTP_200_OK,
    )

class ResearchPaperListAPIView(generics.ListAPIView):
    queryset = ResearchPaper.objects.all()
    serializer_class = ResearchPaperSerializer


class ResearchPaperDetailAPIView(generics.RetrieveAPIView):
    queryset = ResearchPaper.objects.all()
    serializer_class = ResearchPaperSerializer


def secure_image(request, token):
    """Validates a signed token and serves/redirects to the corresponding image."""
    try:
        data = signing.loads(token, max_age=3600)  # token valid for 1 hour
    except signing.BadSignature:
        raise Http404("Invalid or expired image token.")

    try:
        img = ImageNodes.objects.get(id=data["img_id"])
    except ImageNodes.DoesNotExist:
        raise Http404("Image not found.")

    if img.image_file:
        return FileResponse(img.image_file.open("rb"), content_type="image/jpeg")
    return redirect(img.link)


from search_database.ai.graph_generator import generate_graph_from_text

@api_view(["POST"])
def generate_graph_view(request):
    """
    On-demand endpoint to extract a JSON graph (nodes/edges) from a provided text.
    Typically used by the frontend after receiving the main LLM response to visualize concepts.
    """
    try:
        text = request.data.get("text", "")
        if not text:
            return Response({"error": "text is required to generate a graph."}, status=status.HTTP_400_BAD_REQUEST)
            
        graph_data = generate_graph_from_text(text)
        
        if "error" in graph_data:
            return Response(graph_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        return Response(graph_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in generate_graph_view: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

