import re
from difflib import SequenceMatcher

from chatbot.models import FAQ


def get_faq_response(user_message):

    # Convert text to a standard format for comparison.This removes punctuation, extra spaces, and uppercase differences.
    def normalize(text):
        text = text.lower()
        text = re.sub(r"[^\w\s]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    # Normalize the customer's message before searching.
    user_question = normalize(user_message)

    
    if not user_question:
        return None

    # Retrieve only active FAQs from the database.
    faqs = FAQ.objects.filter(is_active=True)

    best_match = None
    best_score = 0

    # Compare the customer's question with every stored FAQ question.
    for faq in faqs:

        faq_question = normalize(faq.question)

        # Calculate similarity between 0 and 1.A score of 1 means the questions are identical.
        score = SequenceMatcher(
            None,
            user_question,
            faq_question
        ).ratio()

        # Keep track of the FAQ with the highest similarity.
        if score > best_score:
            best_score = score
            best_match = faq

    # Return the answer only if similarity reaches 65%.
    if best_match and best_score >= 0.65:
        return best_match.answer

    return None