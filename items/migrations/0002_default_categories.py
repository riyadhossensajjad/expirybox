from django.db import migrations

CATEGORIES = [
    ("Groceries", "Rice, flour, lentils, snacks and other pantry food."),
    ("Dairy & eggs", "Milk, yogurt, cheese, butter, eggs."),
    ("Fruit & vegetables", "Fresh produce."),
    ("Bakery", "Bread, cakes, biscuits."),
    ("Beverages", "Juice, soft drinks, tea, coffee."),
    ("Frozen", "Frozen meat, fish, ready meals."),
    ("Medicine", "Tablets, syrups, first-aid supplies."),
    ("Personal care", "Cosmetics, skincare, toiletries."),
    ("Baby care", "Formula, baby food, diapers."),
    ("Household", "Cleaning supplies, batteries, filters."),
]


def add(apps, schema_editor):
    Category = apps.get_model("items", "Category")
    for name, desc in CATEGORIES:
        Category.objects.get_or_create(category_name=name, defaults={"description": desc})


def remove(apps, schema_editor):
    apps.get_model("items", "Category").objects.filter(
        category_name__in=[c[0] for c in CATEGORIES]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("items", "0001_initial")]
    operations = [migrations.RunPython(add, remove)]
