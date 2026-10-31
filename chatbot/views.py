import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie

from chatbot.services.chat_service import get_chat_response
from chatbot.services.order_service import get_customer_order_context


@ensure_csrf_cookie
def chatbot_csrf(request):
    return JsonResponse({"message": "CSRF cookie set."})

@require_POST
def chat_api(request):

    # Read the customer's message
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "Invalid request data."},
            status=400,
        )

    user_message = data.get("message", "")

    if not isinstance(user_message, str):
        return JsonResponse({"error": "Invalid message."}, status=400)

    user_message = user_message.strip()

    if not user_message or len(user_message) > 1000:
        return JsonResponse(
            {"error": "Message must contain 1–1000 characters."},
            status=400,
        )

    # Get the conversation from the current session
    history = request.session.get("chat_history", [])

    # Add the customer's message
    history.append({
        "role": "user",
        "content": user_message,
    })

    # Keep only the latest 10 messages
    history = history[-10:]

    # Add instructions for the AI assistant
    messages = [
        {
            "role": "system",
            "content": (
                "You are VERDÉ's gardening and customer support assistant. "
                "Answer gardening questions helpfully. "
                "Never invent store prices, stock, policies, or order details. "
                "For information you cannot verify, direct customers "
                "to VERDÉ customer support."
            ),
        },
        *history,
    ]

    order_context = get_customer_order_context(request.user,user_message,)

    # Generate the response using Groq or FAQ fallback
    response = get_chat_response(messages, user_message,order_context,)

    # Save the conversation in the session
    history.append({
        "role": "assistant",
        "content": response,
    })

    request.session["chat_history"] = history[-10:]

    return JsonResponse({"response": response})