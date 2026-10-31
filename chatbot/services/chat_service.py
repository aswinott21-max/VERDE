from chatbot.services.groq_service import generate_chat_response
from chatbot.services.faq_service import get_faq_response
from chatbot.services.product_catalogue_service import (get_product_catalogue_context,is_product_catalogue_query,)

def get_chat_response(messages, user_message, order_context=None):

    # Prioritize verified order information.
    if order_context:
        if order_context.startswith("No matching order"):
            return order_context

        return "Here are the order details from your VERDÉ account:\n\n" + order_context

    # Retrieve actual catalogue data for product-related questions.
    product_context = None

    if is_product_catalogue_query(user_message):
        product_context = get_product_catalogue_context(user_message)

    # Give Groq verified product information.
    if product_context:
        messages = messages + [{
            "role": "system",
            "content": (
                "Use only the following verified VERDÉ catalogue data "
                "when discussing products, prices, and availability. "
                "Do not invent products or alter prices or stock details.\n\n"
                + product_context
            ),
        }]

    response = generate_chat_response(messages)

    if response:
        return response

    # Return verified catalogue data if Groq is unavailable.
    if product_context:
        return product_context

    faq_response = get_faq_response(user_message)

    if faq_response:
        return faq_response

    return (
        "I'm sorry, I couldn't find an answer right now. "
        "Please contact VERDÉ customer support for assistance."
    )
