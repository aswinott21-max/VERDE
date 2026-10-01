from .category_service import get_product_type

def get_product_edit_data(product):
   #check parent
    product_type = get_product_type(product)

    # Prepare the common product data used by all product types.
    data = {
        "id" : product.id,
        "name" : product.name,
        "description": product.description,
        "category_id" : product.category_id,
        "regular_price" : str(product.regular_price),
        "stock_quantity":product.stock_quantity,
        "low_stock_threshold" : product.low_stock_threshold, 
        "is_featured" : product.is_featured,
        "product_type" : product_type,
        "images" : [],
        "variants" :[]
    }
    # Get images directly attached to the product.
    product_images = product.product_images.all().order_by("sort_order")

    # Get images directly attached to the product.
    for image in product_images:
        data["images"].append({
            "id":image.id,
            "url" : image.image_url.url,
            "is_primary" : image.is_primary,
            "sort_order":image.sort_order
        })

    
    if product_type == "pot":

        # Get all variants belonging to this pot.
        variants = product.variants.all().order_by("id")

        # Prepare each variant for the Edit modal.
        for variant in variants:

            # Get the images belonging to this variant.
            variant_images = variant.images.all().order_by("sort_order")

            data["variants"].append({
                "id" : variant.id,
                "color" : variant.color,
                "size" : variant.size,
                "price" :str(variant.price),
                "stock_quantity" : variant.stock_quantity,
                "low_stock_threshold" : variant.low_stock_threshold,
                "images" : [
                    {
                        "id" : image.id,
                        "url": image.image_url.url,
                        "is_primary" : image.is_primary,
                        "sort_order" : image.sort_order
                    }
                    for image in variant_images
                ]
            })
    return data