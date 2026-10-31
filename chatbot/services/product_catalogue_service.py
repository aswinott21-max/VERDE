
from django.db.models import Q

from products.models import Product
from products.services.product_price_service import get_product_sale_price


def is_product_catalogue_query(user_message):
    message = user_message.lower()

    keywords = (
        "product", "products", "sell", "selling",
        "buy", "purchase", "recommend", "recommendation",
        "price", "cost", "available", "availability",
        "stock", "plant", "plants", "indoor", "outdoor",
        "pot", "pots", "ceramic", "equipment", "equipments",
        "tools", "scissors", "trowels",
    )

    return any(keyword in message for keyword in keywords)


def get_product_catalogue_context(user_message, limit=5):
    """
    Return verified product information for chatbot recommendations.
    """

    message = user_message.lower().strip()

    products = (
        Product.objects.filter(
            is_active=True,
            category__is_active=True,
        )
        .select_related("category", "category__parent")
        .prefetch_related("variants")
        .distinct()
    )

    # Identify category-specific requests.
    if "indoor" in message:
        products = products.filter(
            category__name__iexact="Indoor Plants"
        )

    elif "outdoor" in message:
        products = products.filter(
            category__name__iexact="Outdoor Plants"
        )

    elif any(word in message for word in ("plant", "plants")):
        products = products.filter(
            Q(category__name__iexact="Plants")
            | Q(category__parent__name__iexact="Plants")
        )

    elif any(word in message for word in ("pot", "pots", "ceramic")):
        products = products.filter(
            Q(category__name__iexact="Pots")
            | Q(category__parent__name__iexact="Pots")
        )

    elif any(word in message for word in (
        "equipment", "equipments", "tools", "scissors", "trowels"
    )):
        products = products.filter(
            Q(category__name__iexact="Equipments")
            | Q(category__parent__name__iexact="Equipments")
        )

    # Search product names and descriptions when relevant.
    search_terms = [
        word for word in message.split()
        if len(word) > 3
    ]

    if not any(
        keyword in message
        for keyword in (
            "indoor", "outdoor", "plant", "plants",
            "pot", "pots", "ceramic", "equipment",
            "equipments", "tools", "scissors", "trowels",
        )
    ) and search_terms:

        search_filter = Q()

        for word in search_terms:
            search_filter |= (
                Q(name__icontains=word)
                | Q(description__icontains=word)
            )

        matching_products = products.filter(search_filter)

        if matching_products.exists():
            products = matching_products

    products = products.order_by(
        "-is_featured", "-created_at"
    )[:limit]

    if not products:
        return "No matching active products were found in the VERDÉ catalogue."

    results = []

    for product in products:
        variants = [
            variant for variant in product.variants.all()
            if variant.is_active
        ]

        if variants:
            available_variants = [
                variant for variant in variants
                if variant.stock_quantity > 0
            ]

            availability = (
                "Available variants: "
                + ", ".join(
                    f"{variant.color} / {variant.size} "
                    f"(₹{variant.price}, stock: {variant.stock_quantity})"
                    for variant in available_variants
                )
                if available_variants
                else "Currently out of stock"
            )

        else:
            availability = (
                f"In stock: {product.stock_quantity}"
                if product.stock_quantity > 0
                else "Currently out of stock"
            )

        results.append(
            f"Product: {product.name}\n"
            f"Category: {product.category.name}\n"
            f"Price: ₹{get_product_sale_price(product)}\n"
            f"Availability: {availability}\n"
            f"Description: {product.description}"
        )

    return "\n\n".join(results)
