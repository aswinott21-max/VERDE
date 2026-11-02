from chatbot.services.groq_service import generate_chat_response
from chatbot.services.faq_service import get_faq_response
from chatbot.services.product_catalogue_service import (get_product_catalogue_context,is_product_catalogue_query,)


def get_chat_response(messages, user_message, order_context=None):

    # Prioritize verified order information.
    if order_context:
        if order_context.startswith("No matching order"):
            return order_context

        return (
            "Here are the order details from your VERDÉ account:\n\n"
            + order_context
        )

    # Return verified catalogue data directly.
    # Do not let Groq rewrite product information.
    if is_product_catalogue_query(user_message):
        return get_product_catalogue_context(user_message)

    # Use Groq for general conversation and gardening questions.
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
