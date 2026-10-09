import logging
from decimal import Decimal

from products.models import Product
from products.services.category_service import get_product_type


logger = logging.getLogger(__name__)


def calculate_tax(product: Product, amount: Decimal) -> Decimal:
    product_type = get_product_type(product)

    if product_type == "plant":
        tax_rate = Decimal("0")
    elif product_type in ("pot", "equipment"):
        tax_rate = Decimal("0.18")
    else:
        logger.warning("Unable to calculate tax for product %s with an unrecognized category.",product.id,)
        raise ValueError("Product category must be Plants, Pots, or Equipments.")

    tax_amount = (amount * tax_rate).quantize(Decimal("0.01"))
    logger.info("Calculated tax for product %s: %s",product.id,tax_amount,)
    return tax_amount
