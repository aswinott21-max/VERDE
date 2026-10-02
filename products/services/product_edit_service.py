from .category_service import get_product_type

def get_product_edit_data(product):
 
    product_type = get_product_type(product)

    data = {
        "id" : product.id,
        "name" : product.name,
        "description": product.description,
        "category_id" : product.category_id,
        "regular_price" : str(product.regular_price),
        "stock_quantity":product.stock_quantity,
        "low_stock_threshold" : product.low_stock_threshold, 
        "max_purchase_quantity": product.max_purchase_quantity,
        "is_featured" : product.is_featured,
        "product_type" : product_type,
        "images" : [],
        "variants" :[]
    }
  
    product_images = product.product_images.all().order_by("sort_order")

    for image in product_images:
        data["images"].append({
            "id":image.id,
            "url" : image.image_url.url,
            "is_primary" : image.is_primary,
            "sort_order":image.sort_order
        })

    
    if product_type == "pot":

       
        variants = product.variants.all().order_by("id")

        for variant in variants:

            
            variant_images = variant.images.all().order_by("sort_order")

            data["variants"].append({
                "id" : variant.id,
                "color" : variant.color,
                "size" : variant.size,
                "price" :str(variant.price),
                "stock_quantity" : variant.stock_quantity,
                "low_stock_threshold" : variant.low_stock_threshold,
                "max_purchase_quantity": variant.max_purchase_quantity,
                "images" : [
                    {
                        "id" : image.id,
                        "url": image.image_url.url,
                        "is_primary" : image.is_primary,
                        "sort_order" : image.sort_order
                    }
                    for image in variant_images]})
    return data