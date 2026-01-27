from PIL import Image
from django.core.exceptions import ValidationError


def validate_image_format(value):
    """Custom validator to check if image format is either PNG or JPG."""
    try:
        img = Image.open(value)
        if img.format not in ['PNG', 'JPEG']:  # Allow only PNG and JPG (JPEG)
            raise ValidationError("Image must be in PNG or JPG format.")
    except Exception:
        raise ValidationError("Invalid image file.")
