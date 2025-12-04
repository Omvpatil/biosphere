from django.apps import AppConfig

import os
import pandas as pd
from haystack_integrations.components.generators.ollama import OllamaChatGenerator
from haystack.dataclasses import ChatMessage


def __init__():
    generator = OllamaChatGenerator(
        model="gemma3:4b",
        url="http://localhost:11434",
        generation_kwargs={
            "num_predict": 100,
            "temperature": 0.9,
        },
    )


def rag_chat():
    messages = [
        ChatMessage.from_system("\nYou are a helpful, respectful and honest assistant"),
        ChatMessage.from_user("What's Natural Language Processing?"),
    ]
