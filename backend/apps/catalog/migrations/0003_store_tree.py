from django.db import migrations


def forwards(apps, schema_editor):
    from apps.catalog.store_tree import DEFAULT_FROM_KIT_CATEGORY, build_tree

    StoreCategory = apps.get_model("catalog", "StoreCategory")
    Product = apps.get_model("catalog", "Product")
    build_tree(StoreCategory)
    for kit_slug, store_slug in DEFAULT_FROM_KIT_CATEGORY.items():
        target = StoreCategory.objects.get(slug=store_slug)
        Product.objects.filter(category__slug=kit_slug, store_category__isnull=True).update(store_category=target)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0002_store_category")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
