
from chatbot.services.groq_service import generate_chat_response
from chatbot.services.faq_service import get_faq_response


def get_chat_response(messages, user_message, order_context=None):

    # Return verified order information without AI-generated details.
    if order_context:
        if order_context.startswith("No matching order"):
            return order_context

        return "Here are the order details from your VERDÉ account:\n\n" + order_context

    # Try Groq for general questions.
    response = generate_chat_response(messages)

    if response:
        return response

    # Use the FAQ database if Groq is unavailable.
    faq_response = get_faq_response(user_message)

    if faq_response:
        return faq_response

    return (
        "I'm sorry, I couldn't find an answer right now. "
        "Please contact VERDÉ customer support for assistance."
    )
