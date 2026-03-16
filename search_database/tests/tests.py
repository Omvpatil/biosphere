from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from search_database.models import ResearchPaper, DocumentChunks, Author
import numpy as np

class SearchTestViewTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.author = Author.objects.create(name="Test Author")
        self.paper = ResearchPaper.objects.create(title="Test Paper", link="http://test.com")
        self.paper.authors.add(self.author)
        
        # Create a dummy embedding (1024 dimensions)
        dummy_embedding = np.zeros(1024).tolist()
        
        self.chunk = DocumentChunks.objects.create(
            paper=self.paper,
            chunk_index=1,
            text_content="This is a test chunk.",
            embedding=dummy_embedding
        )

    def test_functions_view(self):
        url = reverse('test_functions')
        data = {'user_query': 'test query'}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('top_chunks', response.data)
        self.assertEqual(len(response.data['top_chunks']), 1)
        self.assertEqual(response.data['top_chunks'][0]['chunk_index'], 1)
