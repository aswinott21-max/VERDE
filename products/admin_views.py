import json
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .models import Product, ProductImage, ProductVariant
from catalog.models import Category

from adminpanel.decorators import admin_required

from .services.product_image_validation import (validate_product_images)
from .services.plant_product_validation import (validate_plant_product_data)
from .services.pot_product_validation import (validate_pot_product_data,validate_pot_images)
from .services.equipment_product_validation import(validate_equipment_product_data,validate_equipment_images)
from .services.category_service import (get_subcategories_by_parent,get_subcategory_by_parent, get_product_type)
from .services.product_edit_service import get_product_edit_data
from .services.product_price_service import get_product_sale_price


@never_cache
@admin_required
def product_dashboard(request):

    search = request.GET.get("search", "").strip()#get search text from url
    #products newest first
    products = Product.objects.select_related("category").order_by("-created_at") 

    if search:
        products = products.filter(name__icontains=search)

    #5 products per page    
    paginator = Paginator(products,5)

    page_number = request.GET.get("page")

    page_obj = paginator.get_page(page_number)


   
    current_time = timezone.now()

    # Calculate sale price and check offer status for products on the current page.
    for product in page_obj:
        product.sale_price = get_product_sale_price(product)

        # Check whether the product currently has an active offer.
        product.has_active_offer = (
            product.product_offer > 0
            and (
                product.offer_start_at is None
                or current_time >= product.offer_start_at
            )
            and (
                product.offer_ends_at is None
                or current_time <= product.offer_ends_at
            )
        )

    # Fetch active parent categories for selecting product type
    parent_categories = Category.objects.filter(is_active=True, parent__isnull=True).order_by("id")

    # Fetch active sub-categories for the product form
    plant_categories = get_subcategories_by_parent("Plant")
    pot_categories = get_subcategories_by_parent("Pots")
    equipment_categories = get_subcategories_by_parent("Equipment")

    return render(request, "products/admin_product_dashboard.html", {
        "products": page_obj,
        "page_obj": page_obj,
        "search": search,
        "parent_categories": parent_categories,
        "plant_categories": plant_categories,
        "pot_categories": pot_categories,
        "equipment_categories": equipment_categories,
    })



@admin_required
@require_POST
def add_product(request):

    name = request.POST.get("name")
    description = request.POST.get("description")
    regular_price = request.POST.get("regular_price")
    category_id = request.POST.get("category_id")
    stock_quantity = request.POST.get("stock_quantity")
    low_stock_threshold = request.POST.get("low_stock_threshold")
    is_featured = request.POST.get("is_featured") == "true"
    max_purchase_quantity = request.POST.get("max_purchase_quantity")

    # Validate Plant product data.
    error = validate_plant_product_data(name,description,category_id,regular_price,stock_quantity,low_stock_threshold,max_purchase_quantity)

    if error:
        return JsonResponse({
            "success": False,
            "message": error,
            "data": None
        }, status=400)

    # Product must belong to an active subcategory.
    category = get_subcategory_by_parent(category_id,"Plant")
    product = Product.objects.create(
        name=name.strip(),
        description=description,
        regular_price=regular_price,
        stock_quantity = stock_quantity,
        low_stock_threshold = low_stock_threshold,
        max_purchase_quantity = max_purchase_quantity,
        is_featured = is_featured,
        category = category

    )

    return JsonResponse({
        "success": True,
        "message": "Product created successfully.",
        "data": {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "regular_price": str(product.regular_price),
            "category_id": product.category_id
        }}, status=201)


@admin_required
@require_POST
def add_pot_product(request):

    name = request.POST.get("name")
    description = request.POST.get("description")
    category_id = request.POST.get("category_id")
    is_featured = request.POST.get("is_featured")=="true"

    variants_data = request.POST.get("variants","[]")

    try:
        variants = json.loads(variants_data)
    except (TypeError,json.JSONDecodeError):
        variants = []

    # Get the common product images.
    product_images = request.FILES.getlist("product_images")

    # Get one image for each variant.
    variant_images = [
        request.FILES.get(f"variant_image_{index}")
        for index in range(len(variants))
    ]

    # Validate the basic pot data and variants.
    error = validate_pot_product_data(name,description,category_id,variants)

    if error:
        return JsonResponse({
            "success" : False,
            "message" :error,
            "data" : None
        }, status=400)

    # Validate common product images and variant images.
    error = validate_pot_images(product_images,variant_images)

    if error:
        return JsonResponse({
            "success": False,
            "message": error,
            "data": None
        }, status=400)


    # check the selected category is an active subcategory.
    category = get_subcategory_by_parent(category_id,"Pot")

    # Create the pot and all related records as one transaction.
    with transaction.atomic():

        product = Product.objects.create(
            name= name.strip(),
            description = description.strip(),
            regular_price = 0,
            stock_quantity=0,
            low_stock_threshold=0,
            is_featured =is_featured,
            category=category
        )
        total_stock = 0
        lowest_price = None

        # Create every variant belonging to this pot.
        for index,variant in enumerate(variants):

            product_variant = ProductVariant.objects.create(
                product = product,
                color = variant["color"].strip(),
                size = variant["size"].strip(),
                price = variant["price"],
                stock_quantity=variant["stock"],
                low_stock_threshold=variant["low_stock_threshold"],
                max_purchase_quantity = variant["max_purchase_quantity"]
            )

            # Save the image belonging to this variant.
            ProductImage.objects.create(
                product_variant=product_variant,
                image_url = variant_images[index],
                is_primary = True,
                sort_order = 0
            )

            # Add variant stock to the total product quantity.
            total_stock += int(variant["stock"])

            # Find the lowest variant price.
            if lowest_price is None or product_variant.price< lowest_price:
                lowest_price = product_variant.price

        # Store the calculated total stock and lowest variant price.
        product.stock_quantity = total_stock
        product.regular_price = lowest_price
        product.save()

        # Save the common product images.
        for index, image in enumerate(product_images):
            ProductImage.objects.create(
                product=product,
                image_url = image,
                is_primary = (index == 0),
                sort_order = index
            )

    return JsonResponse({"success": True,
        "message": "Pot product created successfully.",
        "data": {
            "id": product.id,
            "name": product.name,
            "category_id": product.category_id,
            "regular_price": str(product.regular_price),
            "stock_quantity": product.stock_quantity,
            "variant_count": product.variants.count()
        }
    }, status=201 )




@admin_required
@require_POST
def add_equipment_product(request):

    name = request.POST.get("name")
    description = request.POST.get("description")
    regular_price = request.POST.get("regular_price")
    category_id = request.POST.get("category_id")
    stock_quantity = request.POST.get("stock_quantity")
    low_stock_threshold = request.POST.get("low_stock_threshold")
    max_purchase_quantity = request.POST.get("max_purchase_quantity")
    is_featured = request.POST.get("is_featured") == "true"

    product_images = request.FILES.getlist("product_images")

    error = validate_equipment_product_data(name, description, category_id, regular_price, stock_quantity, low_stock_threshold,max_purchase_quantity)

    if error:
        return JsonResponse({
            "success" : False,
            "message" : error,
            "data" : None
        }, status=400)

    error = validate_equipment_images(product_images)

    if error:
        return JsonResponse({
            "success" : False,
            "message":error,
            "data" : None
        }, status=400)

    # Check that the selected category is an active subcategory.
    category = get_subcategory_by_parent(category_id,"Equipment")

    # Create the equipment product and its images as one transaction.
    with transaction.atomic():

        # Create the main equipment product.
        product = Product.objects.create(
            name = name.strip(),
            description = description.strip(),
            regular_price = regular_price,
            stock_quantity = stock_quantity,
            low_stock_threshold = low_stock_threshold,
            max_purchase_quantity = max_purchase_quantity,
            is_featured = is_featured,
            category = category
        )
        # Save all equipment product images.
        for index, image in enumerate(product_images):
            ProductImage.objects.create(
                product=product,
                image_url = image,
                is_primary =(index == 0),
                sort_order = index
            )

    return JsonResponse({
        "success":True,
        "message" : "Equipment product created successfully.",
        "data" : {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "regular_price": str(product.regular_price),
            "stock_quantity": product.stock_quantity,
            "low_stock_threshold": product.low_stock_threshold,
            "max_purchase_quantity": product.max_purchase_quantity,
            "category_id": product.category_id,
            "is_featured": product.is_featured,
            "image_count": len(product_images)
        }
    }, status=201)



    




@admin_required
@require_POST
def upload_variant_images(request, variant_id):

    # Find the product variant
    variant = get_object_or_404(
        ProductVariant,
        id=variant_id
    )

    # Get all uploaded images
    images = request.FILES.getlist("images")

    error = validate_product_images(images)

    if error:
        return JsonResponse({
            "success": False,
            "message": error,
            "data": None
        }, status=400)

    # Save images to the variant
    for index, image in enumerate(images):
        ProductImage.objects.create(
            product_variant=variant,
            image_url=image,
            is_primary=(index == 0),
            sort_order=index
        )

    return JsonResponse({
        "success": True,
        "message": "Product variant images uploaded successfully.",
        "data": {
            "variant_id": variant_id,
            "image_count": len(images)
        }
    })

@admin_required
@require_POST
def upload_product_images(request, product_id):

    # Find the product
    product = get_object_or_404(
        Product,
        id=product_id
    )

    # Get uploaded images
    images = request.FILES.getlist("images")

    # Validate image count
    error = validate_product_images(images)

    if error:
        return JsonResponse({
            "success": False,
            "message": error,
            "data": None
        }, status=400)

    # Save images directly to the product
    for index, image in enumerate(images):
        ProductImage.objects.create(
            product=product,
            image_url=image,
            is_primary=(index == 0),
            sort_order=index
        )

    return JsonResponse({
        "success": True,
        "message": "Product images uploaded successfully.",
        "data": {
            "product_id": product_id,
            "image_count": len(images)
        }
    })


@admin_required
def get_product_edit_data_view(request, product_id):
    # Find the product or return 404.
    product = get_object_or_404(Product, id=product_id)
    # Get all existing data required by the Edit modal.
    data = get_product_edit_data(product)

    return JsonResponse({
        "success" : True,
        "message" : "Product edit data fetched successfully.",
        "data" : data
    })
 



@admin_required
@require_POST
def edit_product(request, product_id):
    # Find the product or return 404.
    product = get_object_or_404(
        Product,
        id=product_id
    )

    # Identify whether the product is a Plant, Pot, or Equipment.
    product_type = get_product_type(product)

    # Handle Plant editing.
    if product_type == "plant":

        # Get updated Plant data.
        name = request.POST.get("name")
        description = request.POST.get("description")
        regular_price = request.POST.get("regular_price")
        category_id = request.POST.get("category_id")
        stock_quantity = request.POST.get("stock_quantity")
        low_stock_threshold = request.POST.get("low_stock_threshold")
        max_purchase_quantity = request.POST.get("max_purchase_quantity")
        is_featured = request.POST.get("is_featured") == "true"

        # Get newly added product images
        product_images = request.FILES.getlist("product_images")

        error = validate_plant_product_data(name,description,category_id,regular_price,stock_quantity,low_stock_threshold, max_purchase_quantity)

        if error:
            return JsonResponse({
                "success": False,
                "message": error,
                "data": None
            }, status=400)

        # Count existing images after deletions
        existing_images_count = product.product_images.count()

        # Count newly uploaded images.
        new_images_count = len(product_images)

        # Calculate the final image count
        total_images_count = existing_images_count + new_images_count

        # Validate minimum image count
        if total_images_count < 3:
            return JsonResponse({
                "success": False,
                "message": "At least 3 images required.",
                "data": None
            }, status=400)

        # Validate maximum image count
        if total_images_count > 4:
            return JsonResponse({
                "success": False,
                "message": "Maximum 4 images allowed.",
                "data": None
            }, status=400)

        # Get the selected active Plant subcategory
        category = get_subcategory_by_parent(
            category_id,
            "Plants"
        )

        # Update Plant product fields
        product.name = name.strip()
        product.description = description
        product.regular_price = regular_price
        product.stock_quantity = stock_quantity
        product.low_stock_threshold = low_stock_threshold
        product.max_purchase_quantity = max_purchase_quantity
        product.is_featured = is_featured
        product.category = category

        product.save()

        # Save newly added product images.
        for image in product_images:
            ProductImage.objects.create(
                product=product,
                image_url=image,
                is_primary=False,
                sort_order=ProductImage.objects.filter(
                    product=product
                ).count(),
            )

        return JsonResponse({
            "success": True,
            "message": "Product updated successfully.",
            "data": {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "regular_price": str(product.regular_price),
                "stock_quantity": product.stock_quantity,
                "low_stock_threshold": product.low_stock_threshold,
                "category_id": product.category_id,
                "is_featured": product.is_featured
            }
        }, status=200)

    # Handle Pot editing.
    elif product_type == "pot":

        # Get updated Pot data.
        name = request.POST.get("name")
        description = request.POST.get("description")
        category_id = request.POST.get("category_id")
        is_featured = request.POST.get("is_featured") == "true"

        # Get the submitted variant data.
        variants_data = request.POST.get("variants", "[]")

        # Convert the variant JSON string into Python data.
        try:
            variants = json.loads(variants_data)
        except (TypeError, json.JSONDecodeError):
            variants = []

        # Get newly added common product images.
        product_images = request.FILES.getlist("product_images")

        # Get the IDs of existing common images that were kept.
        existing_image_ids_data = request.POST.get(
            "existing_image_ids",
            "[]"
        )
        # Convert the existing image IDs from JSON into a Python list.
        try:
            existing_image_ids = json.loads(existing_image_ids_data)
        except (TypeError, json.JSONDecodeError):
            existing_image_ids = []

        # Count existing common images that will remain.
        existing_images_count = len(existing_image_ids)

        # Count newly uploaded common images.
        new_images_count = len(product_images)

        # Calculate the final common product image count.
        total_images_count = existing_images_count + new_images_count

        # Validate the minimum common image count.
        if total_images_count < 3:
            return JsonResponse({
                "success" :False,
                "message":"At least 3 product images are reuired.",
                "data" : None
            }, status=400)
        
        # Validate the maximum common image count.
        if total_images_count > 4:
            return JsonResponse({
                "success" : False,
                "message" :"Maximum 4 prodct image are allowed.",
                "data" : None
            }, status=400)        

        # Get newly added variant images.
        variant_images = {
            key: image
            for key, image in request.FILES.items()
            if key.startswith("variant_image_")
        }

        # Validate the basic Pot data and variants.
        error = validate_pot_product_data(
            name,
            description,
            category_id,
            variants
        )

        if error:
            return JsonResponse({
                "success": False,
                "message": error,
                "data": None
            }, status=400)

        # Check that the selected category belongs to the active Pots parent.
        category = get_subcategory_by_parent(
            category_id,
            "Pots"
        )

        # Update the Pot and all related variants as one transaction.
        with transaction.atomic():

            # Get all existing common product images for this Pot.
            existing_product_images = product.product_images.all()

            # Delete common images that were removed from the Edit modal.
            for image in existing_product_images:

                if image.id not in existing_image_ids:
                    # Delete the image file from storage.
                    if image.image_url:
                        image.image_url.delete(save=False)

                    # Delete the image record from the database.
                    image.delete()


            # Save newly added common product images.
            for image in product_images:
                # Get the next image sort order.
                sort_order = product.product_images.count()

                #Save the new product image
                ProductImage.objects.create(
                    product=product,
                    image_url = image,
                    is_primary = (sort_order == 0),
                    sort_order=sort_order
                )



            # Get all existing variants belonging to this Pot.
            existing_variants = {
                variant.id: variant
                for variant in product.variants.all()
            }


            # Store the IDs of variants submitted by the Edit modal.
            submitted_variant_ids = set()

            # Update existing variants or create new variants.
            for variant_data in variants:

                variant_id = variant_data.get("id")

                # Update an existing variant.
                if variant_id:

                    variant = existing_variants.get(
                        int(variant_id)
                    )

                    # Reject a variant ID that does not belong to this product.
                    if not variant:
                        return JsonResponse({
                            "success": False,
                            "message": "Invalid product variant.",
                            "data": None
                        }, status=400)

                    variant.color = variant_data["color"].strip()
                    variant.size = variant_data["size"].strip()
                    variant.price = variant_data["price"]
                    variant.stock_quantity = variant_data["stock"]
                    variant.low_stock_threshold = (variant_data["low_stock_threshold"])
                    variant.max_purchase_quantity = (variant_data["max_purchase_quantity"])
                    variant.save()

                    # Remember that this existing variant is still being used.
                    submitted_variant_ids.add(variant.id)

                    # Get a newly uploaded image for this existing variant.
                    new_variant_image = variant_images.get(
                        f"variant_image_{variant.id}"
                    )

                    # Replace the existing variant image when a new image is uploaded.
                    if new_variant_image:

                        # Get the existing variant images.
                        existing_images = variant.images.all().order_by(
                            "sort_order"
                        )

                        # Delete the existing variant images.
                        for image in existing_images:

                            if image.image_url:
                                image.image_url.delete(save=False)

                            image.delete()

                        # Save the new variant image.
                        ProductImage.objects.create(
                            product_variant=variant,
                            image_url=new_variant_image,
                            is_primary=True,
                            sort_order=0
                        )

                # Create a new variant.
                else:

                    variant = ProductVariant.objects.create(
                        product=product,
                        color=variant_data["color"].strip(),
                        size=variant_data["size"].strip(),
                        price=variant_data["price"],
                        stock_quantity=variant_data["stock"],
                        low_stock_threshold=variant_data["low_stock_threshold"],
                        max_purchase_quantity=variant_data["max_purchase_quantity"])

                    # Remember the newly created variant.
                    submitted_variant_ids.add(variant.id)

                    # Get the newly uploaded image for this new variant.
                    new_variant_image = variant_images.get(
                        f"variant_image_{variant_data.get('temp_id')}"
                    )

                    # Save the image for the newly created variant.
                    if new_variant_image:

                        ProductImage.objects.create(
                            product_variant=variant,
                            image_url=new_variant_image,
                            is_primary=True,
                            sort_order=0
                        )

            # Delete variants that were removed from the Edit modal.
            for variant_id, variant in existing_variants.items():

                if variant_id not in submitted_variant_ids:
                    variant.delete()

            # Get all active variants after the updates.
            active_variants = product.variants.filter(
                is_active=True
            )

            # Calculate the total stock of all active variants.
            total_stock = sum(
                variant.stock_quantity
                for variant in active_variants
            )

            # Find the lowest price among active variants.
            lowest_price = min(
                variant.price
                for variant in active_variants
            )

            # Update the Pot's calculated product-level values.
            product.regular_price = lowest_price
            product.stock_quantity = total_stock
            product.category = category
            product.name = name.strip()
            product.description = description.strip()
            product.is_featured = is_featured

            product.save()

        return JsonResponse({
            "success": True,
            "message": "Pot product updated successfully.",
            "data": {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "regular_price": str(product.regular_price),
                "stock_quantity": product.stock_quantity,
                "category_id": product.category_id,
                "is_featured": product.is_featured,
                "variant_count": product.variants.count()
            }
        }, status=200)


    elif product_type =="equipment":

        # Get updated Equipment data.
        name = request.POST.get("name")
        description = request.POST.get("description")
        regular_price = request.POST.get("regular_price")
        category_id = request.POST.get("category_id")
        stock_quantity = request.POST.get("stock_quantity")
        low_stock_threshold = request.POST.get("low_stock_threshold")
        max_purchase_quantity = request.POST.get("max_purchase_quantity")
        is_featured = request.POST.get("is_featured") == "true"

        #Get newly added product images.
        product_images = request.FILES.getlist("product_images")

        #Get the IDs of existing common images that were kept.
        existing_image_ids_data = request.POST.get("existing_image_ids", "[]")

        # Convert the existing image IDs from JSON into a Python list
        try:
            existing_image_ids = json.loads(existing_image_ids_data)
        except (TypeError, json.JSONDecodeError):
            existing_image_ids = []

        # Validate the basic Equipment data.
        error = validate_equipment_product_data(name, description, category_id, regular_price, stock_quantity, low_stock_threshold,max_purchase_quantity)

        if error:
            return JsonResponse({
                "success" : False,
                "message": error,
                "data" : None
            }, status=400)

        # Count existing images that will remain.
        existing_images_count = len(existing_image_ids)

        # Count newly uploaded images.
        new_images_count = len(product_images)

        # Calculate the final image count.
        total_images_count = existing_images_count + new_images_count

        # Validate minimum image count.
        if total_images_count<3:
            return JsonResponse({
                "success" : False,
                "message" :"At least 3 product images are required.",
                "data" : None
            }, status=400)

        # Validate maximum image count.
        if total_images_count > 4:
            return JsonResponse({
                "succces": False,
                "message" : "Maximum 4 product images are allowed",
                "data" : None
            }, status=400)

        # Check that the selected category belongs to the active Equipments parent.
        category = get_subcategory_by_parent(category_id, "Equipments")

        # Update the Equipment and its images as one transaction.
        with transaction.atomic():
            # Get all existing common product images for this Equipment.
            existing_product_images = product.product_images.all()

            # Delete images that were removed from the Edit modal.
            for image in existing_product_images:
                if image.id not in existing_image_ids:
                    # Delete the image file from storage
                    if image. image_url:
                        image.image_url.delete(save=False)

                    # Delete the image record from the database.
                    image.delete()

            # Update Equipment product fields.
            product.name = name.strip()
            product.description = description.strip()
            product.regular_price = regular_price
            product.stock_quantity = stock_quantity
            product.low_stock_threshold = low_stock_threshold
            product.max_purchase_quantity = max_purchase_quantity
            product.is_featured = is_featured
            product.category = category

            product.save()

            # Save newly added product images.
            for image in product_images:

                # Get the next image sort order.
                sort_order = product.product_images.count()

                ProductImage.objects.create(
                    product=product,
                    image_url=image,
                    is_primary=(sort_order ==0),
                    sort_order=sort_order 
                )
        return JsonResponse({
                        "success": True,
            "message": "Equipment product updated successfully.",
            "data": {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "regular_price": str(product.regular_price),
                "stock_quantity": product.stock_quantity,
                "low_stock_threshold": product.low_stock_threshold,
                "category_id": product.category_id,
                "is_featured": product.is_featured
            }
        }, status=200)

                    







    else:
        return JsonResponse({
            "success": False,
            "message": "This product type is not handled yet.",
            "data": None
        }, status=400)



    

@admin_required
@require_POST
def delete_product_image_view(request, product_id, image_id):
    # Find the image belonging to the selected product.
    image = get_object_or_404(ProductImage, id=image_id, product_id=product_id)

    # Delete the image file from storage.
    if image.image_url:
        image.image_url.delete(save=False)

    image.delete()

    return JsonResponse ({
        "success" : True, 
        "message":"Product image deleted successdully.",
        "data":{
            "product_id" : product_id,
            "image_id" : image_id
        }
    }, status=200)




@admin_required
@require_POST
def toggle_product_status(request, product_id):
    #Find the product
    product = get_object_or_404(Product, id=product_id)

    # Toggle active status
    product.is_active = not product.is_active

    product.save() #save changes

    status =  "listed" if product.is_active else "unlisted"

    return JsonResponse({
        "success" :True,
        "message" : f"Product{status} successfully.",
        "data" : {
            "id" : product.id,
            "is_active" : product.is_active
            }
    })


@admin_required
@require_POST
def set_product_offer(request, product_id):
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Only POST requests are allowed.",
                "data": None
            },
            status=405
        )

    product = get_object_or_404(Product, id=product_id)

    discount_value = request.POST.get("discount_value")
    offer_start_at = request.POST.get("offer_start_at")
    offer_end_at = request.POST.get("offer_end_at")
    time_zone_name = request.POST.get("time_zone")

    remove_offer = request.POST.get("remove_offer")

    # Remove existing product offer.
    if remove_offer == "true":
        product.product_offer = 0
        product.offer_start_at = None
        product.offer_ends_at = None
        product.save()

        return JsonResponse(
            {
                "success": True,
                "message": "Product offer removed successfully.",
                "data": {
                    "product_id": product.id
                }
            }
        )

    # Check that all offer fields are provided.
    if not discount_value:
        return JsonResponse({
            "success": False,
            "message": "Discount is required.",
            "data": None
        }, status=400)

    if not offer_start_at:
        return  JsonResponse({
            "success": False,
            "message": "Offer start date is required.",
            "data": None
        }, status=400)
    
    if not offer_end_at:
        return JsonResponse({
            "success": False,
            "message": "Offer end date is required.",
            "data": None
        }, status=400)

    try:
        discount_value = Decimal(discount_value)
    except(InvalidOperation,TypeError):
        return JsonResponse({
            "success": False,
            "message": "Discount must be a valid number.",
            "data": None
        }, status=400)  

    if discount_value <= 0 or discount_value > 100:
        return JsonResponse({
            "success": False,
            "message": "Discount must be between 0.01% and 100%.",
            "data": None
        }, status=400)

    # Convert the submitted datetime values into Python datetime objects.
    start_datetime=parse_datetime(offer_start_at)
    end_datetime=parse_datetime(offer_end_at)

    if start_datetime is None:
        return JsonResponse({
            "success": False,
            "message": "Invalid offer start date.",
            "data": None
        },status=400)
    if end_datetime is None:
        return JsonResponse({
            "success": False,
            "message": "Invalid offer end date.",
            "data": None
        }, status=400)
    
    try:
        offer_timezone = ZoneInfo(time_zone_name) if time_zone_name else timezone.get_current_timezone()
    except ZoneInfoNotFoundError:
        return JsonResponse({
            "success": False,
            "message": "Invalid offer time zone.",
            "data": None
        }, status=400)

    # Interpret datetime-local values in the timezone of the admin's browser.
    if timezone.is_naive(start_datetime):
        start_datetime = timezone.make_aware(start_datetime, offer_timezone)

    if timezone.is_naive(end_datetime):
        end_datetime = timezone.make_aware(end_datetime, offer_timezone)

    current_time = timezone.now()

    if start_datetime <  current_time:
        return JsonResponse({
            "success" :False,
            "message" : "Offer start date cannot be in past",
            "data" : None
        }, status=400)

    if end_datetime <  current_time:
        return JsonResponse({
            "success": False,
            "message": "Offer end date cannot be in the past.",
            "data": None
        }, status=400)

    

    #check offer has valid time line
    if end_datetime <= start_datetime:
        return JsonResponse({
            "success": False,
            "message": "Offer end date must be after the start date.",
            "data": None
        }, status=400)
    
    #save validated offer
    product.product_offer= discount_value
    product.offer_start_at = start_datetime
    product.offer_ends_at = end_datetime
    product.save()

    return JsonResponse(
        {
          "success": True,
            "message": "Product offer applied successfully.",
            "data": {
                "product_id": product.id,
                "discount_value": str(discount_value),
                "offer_start_at": start_datetime.isoformat(),
                "offer_end_at": end_datetime.isoformat()
            }  
        }
    )
  