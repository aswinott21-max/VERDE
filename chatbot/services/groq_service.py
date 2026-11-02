import logging

from django.conf import settings
from groq import Groq, GroqError

logger = logging.getLogger(__name__)


def generate_chat_response(messages):
    if not settings.GROQ_API_KEY:
        return None

    try:
        client = Groq(api_key=settings.GROQ_API_KEY)

        completion = client.chat.completions.create(
            model=getattr(
                settings,
                "GROQ_MODEL",
                "openai/gpt-oss-20b",
            ),
            messages=messages,
            temperature=0.3,
            max_completion_tokens=500,
        )

        return completion.choices[0].message.content

    except GroqError:
        logger.exception("Groq API request failed.")
        return None