from typing import Dict, Any, Optional, List
import os
from google import genai
from google.genai import types
import openai


class GeminiProvider:
    """Gemini LLM provider for chat completions"""

    def __init__(self, model_name: str = "gemini-2.5-pro", api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            raise ValueError(
                "Gemini API key is required. Set GEMINI_API_KEY environment variable.")

        self.client = genai.Client(api_key=self.api_key)
        self.generation_config = None

    async def generate(self, context: str, system_prompt: Optional[str] = None) -> str:
        """Generate a response from the model"""
        config = None
        if system_prompt:
            config = types.GenerateContentConfig(
                system_instruction=system_prompt)

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=context,
            config=config
        )

        return response.text

    def set_generation_config(self, **kwargs):
        """Update generation configuration"""
        if kwargs:
            self.generation_config = types.GenerateContentConfig(**kwargs)
        else:
            self.generation_config = None


class OpenAIProvider:
    """OpenAI LLM provider for chat completions"""

    # gpt-5-2025-08-07
    # gpt-5-mini-2025-08-07
    def __init__(self, model_name: str = "gpt-5-nano-2025-08-07", api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY environment variable.")

        self.client = openai.OpenAI(api_key=self.api_key)
        self.generation_config = {}

    async def generate(self, context: str, system_prompt: Optional[str] = None) -> str:
        """Generate a response from the model"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": context})

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            **self.generation_config
        )

        return response.choices[0].message.content

    def set_generation_config(self, **kwargs):
        """Update generation configuration"""
        self.generation_config = kwargs
