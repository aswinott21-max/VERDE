from django.db import migrations, models

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    # Apply wallet schema corrections after the initial migration.
    dependencies = [
        ("wallet", "0001_initial"),
    ]
    operations = [
        migrations.AddField(
            model_name="wallet",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.RenameField(
            model_name="wallet",
            old_name="is_acticve",
            new_name="is_active",
        ),
        
    ]
