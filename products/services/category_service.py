from django.shortcuts import get_object_or_404
from django.db.models import Q
from catalog.models import Category

def _find_parent_category(parent_name):
    #Helper to find top-level parent category handling singular/plural and case differences.
    return Category.objects.filter(
        Q(name__iexact=parent_name)
        | Q(name__iexact=f"{parent_name}s")
        | Q(name__iexact=parent_name.rstrip('s'))
        | Q(name__icontains=parent_name),
        parent__isnull=True,is_active=True).first()




def get_subcategories_by_parent(parent_name):
    # Find the active top-level parent category safely 
    parent_category = _find_parent_category(parent_name)
    if not parent_category:
        return Category.objects.none()

    # Return only active subcategories of the selected parent.
    return Category.objects.filter(parent=parent_category, is_active=True).order_by("name")


def get_subcategory_by_parent(category_id, parent_name):
    # Find the active top-level parent category.
    parent_category = _find_parent_category(parent_name)
    if parent_category:
        return get_object_or_404(Category, id=category_id, parent=parent_category, is_active=True)
    return get_object_or_404(Category, id=category_id, is_active=True)


def get_product_type(product):
    # Get the parent category of the product's category.
    parent_category = product.category.parent

    if not parent_category:
        return None

    if parent_category.name.casefold() == "plants":
        return "plant"

    if parent_category.name.casefold() == "pots":
        return "pot"

    if parent_category.name.casefold() == "equipments":
        return "equipment"

    return None

def get_product_type_by_parent_name(parent_name):
    #find the active parent category from the URL name
    parent_category = _find_parent_category(parent_name)
    if not parent_category:
        return None
    category_name = parent_category.name.casefold()
    if category_name in ("plant", "plants"):
        return "Plant"
    if category_name in ("pot","pots"):
        return "Pot"
    if category_name in ("equipment","equipments"):
        return "equipments"
    return None


def get_category_and_subcategory_ids(category_id):

    #Returns the selected category ID and its active direct subcategory IDs.
    category_ids = [category_id]

    subcategory_ids = Category.objects.filter(parent_id=category_id,is_active=True,).values_list("id", flat=True)

    category_ids.extend(subcategory_ids)

    return category_ids