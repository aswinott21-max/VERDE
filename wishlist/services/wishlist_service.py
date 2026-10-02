from wishlist.models import Wishlist, WishlistItem
from products.services.product_price_service import get_product_sale_price

# Get the user's active wishlist.
def get_user_wishlist(user):
    return Wishlist.objects.filter(user=user).first()


# Get or create the user's wishlist.
def get_or_create_user_wishlist(user):
    wishlist, created = Wishlist.objects.get_or_create(user=user,)

    return wishlist

def get_user_wishlist_product_ids(user):
    # Get all active wishlist items from all wishlists belonging to the user.
    return set(
        WishlistItem.objects.filter(wishlist__user=user,is_active=True,).values_list("product_id",flat=True,))


def get_user_wishlist_count(user):
    # Count all active wishlist items belonging to the user.
    return WishlistItem.objects.filter(wishlist__user=user,is_active=True,).count()

def get_user_wishlist_items(user):

    #Get all active wishlist items for the logged-in user.
    wishlist_items = (WishlistItem.objects.filter(wishlist__user=user,is_active=True).select_related("product", "product_variant").prefetch_related("product__product_images","product_variant__images",))

    #Calculate the correct sale price for each wishlist item.
    for item in wishlist_items:
        #Use variant price for Pot products.
        if item.product_variant:
            item.sale_price = get_product_sale_price(item.product,item.product_variant.price)
        else:
            #use the normal product price for Plant/Equipment.
            item.sale_price = get_product_sale_price(item.product)
    
    return wishlist_items



# Add a product/variant to the user's wishlist.
def add_to_wishlist(user, product_id, variant_id=None):

    wishlist = get_or_create_user_wishlist(user)

    # Check whether this product/variant already exists.
    item = WishlistItem.objects.filter(wishlist=wishlist,product_id=product_id,product_variant_id=variant_id,).first()

    # If the item already exists but was inactive, reactivate it.
    if item:
        if not item.is_active:
            item.is_active = True
            item.save(update_fields=["is_active"])

        return item

    # Create a new wishlist item.
    return WishlistItem.objects.create(
        wishlist=wishlist,
        product_id=product_id,
        product_variant_id=variant_id,
        is_active=True,
    )


def remove_from_wishlist(user, product_id, variant_id=None):

    wishlist = get_user_wishlist(user)

    # Nothing to remove if the user has no wishlist.
    if not wishlist:
        return False

    # Find the matching active wishlist item.
    item = WishlistItem.objects.filter(wishlist=wishlist,product_id=product_id,product_variant_id=variant_id,is_active=True,).first()

    if not item:
        return False

    item.delete()

    return True