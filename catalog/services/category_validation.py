import re

def validate_category_data(name, description):
    name = name.strip()
    description= description.strip()

    #required
    if not name:
        return "Category name is required."
    
    if not re.search(r"[A-Za-z]", name):
        return  "Category name must contain letters"

    #cat-name can contain letters, numbers, spaces, &, apostrophe and hyphen.
    if not re.fullmatch(r"[A-Za-z0-9 &'\-]+", name):
        return "Category name contains invalid characters."


    if not description:
        return None #optional

    if not re.search(r"[A-Za-z]",description):
         return "Category description must contain letters."

    return None