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

from biosphere.serializers import ChatMessageSerializer

def sse_event_generator(user_query, chat_history, session=None, request=None):
    try:
        if session:
            # Yield the session id back to the frontend so it can pass it on subsequent follow-ups
            yield f"data: {json.dumps({'type': 'session_id', 'session_id': session.id})}\n\n"

        final_ai_text = ""
        paper_ids = []
        image_ids = []
        for event in stream_llm_response(user_query, chat_history, request=request):
            if event.get("type") == "token":
                final_ai_text += event.get("content", "")
            elif event.get("type") == "data" and "papers" in event:
                # Capture internal database PKs (id) for history persistence
                paper_ids = [p["id"] for p in event["papers"]]
                for p in event["papers"]:
                    if "images" in p:
                        image_ids.extend([img["id"] for img in p["images"]])
                
            yield f"data: {json.dumps(event)}\n\n"
            
        # Post-processing: Save the final AI text with associated metadata
        if session and final_ai_text:
            serializer = ChatMessageSerializer(data={
                "session": session.id,
                "role": ChatRole.ASSISTANT,
                "content": final_ai_text,
                "paper_ids": list(set(paper_ids)),
                "image_ids": list(set(image_ids))
            })
            if serializer.is_valid():
                serializer.save()
            else:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Serializer errors saving message: {serializer.errors}")
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in sse_event_generator: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

@api_view(["POST"])
def chat_search_stream_view(request):
    try:
        data = request.data
        user_query = data.get("user_query")
        session_id = data.get("session_id")
        
        if not user_query:
            return Response({"error": "user_query is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        # 1. Manage ChatSession and Auth Logic
        session = None
        user = request.user if request.user.is_authenticated else None
        
        # Guest Limit: 3 questions per session
        if not user:
            guest_count = request.session.get('guest_query_count', 0)
            if guest_count >= 3:
                return Response({
                    "type": "error",
                    "message": "auth_required",
                    "details": "You've reached the 3-question limit for guests. Please log in to continue."
                }, status=status.HTTP_403_FORBIDDEN)
            request.session['guest_query_count'] = guest_count + 1
        
        if session_id:
            try:
                # Ensure the session belongs to the user if they are logged in
                if user:
                    session = ChatSession.objects.get(id=session_id, user=user)
                else:
                    session = ChatSession.objects.get(id=session_id)
            except ChatSession.DoesNotExist:
                return Response({"error": "Invalid session_id"}, status=status.HTTP_404_NOT_FOUND)
        else:
            # Use the authenticated user, or fallback to first user for demo purposes if requested, 
            # but ideally it should be mandatory if authentication is integrated.
            final_user = user or User.objects.first()
            if final_user:
                session = ChatSession.objects.create(user=final_user, title=user_query[:50])

        # 2. Build lean Chat History from DB
        chat_history = ""
        if session:
            # Build string from previous interactions.
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
            # Fallback if no session was created
            chat_history = data.get("chat_history", "")
        
        response = StreamingHttpResponse(
            sse_event_generator(user_query, chat_history, session=session, request=request),
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
    
    events = list(stream_llm_response(user_query, chat_history, request=request))
    
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
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Token valid for 1 day (86400 seconds)
        data = signing.loads(token, max_age=86400)
    except signing.BadSignature:
        logger.warning(f"Invalid or expired image token: {token}")
        raise Http404("Invalid or expired image token.")

    try:
        img = ImageNodes.objects.get(id=data["img_id"])
    except ImageNodes.DoesNotExist:
        logger.warning(f"Image not found for id: {data.get('img_id')}")
        raise Http404("Image not found.")

    if img.image_file:
        try:
            return FileResponse(img.image_file.open("rb"), content_type="image/jpeg")
        except Exception as e:
            logger.error(f"Failed to open image file {img.image_file.name} for id {img.id}: {e}")
            if img.link and img.link != "Link":
                logger.info(f"Falling back to external link for image {img.id}: {img.link}")
                return redirect(img.link)
            raise Http404("Image file not accessible.")
            
    if img.link and img.link != "Link":
        return redirect(img.link)
        
    raise Http404("No image file or link available.")


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

