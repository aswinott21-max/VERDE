
from django.db import migrations, models


class Migration(migrations.Migration):
    # Correct the existing PostgreSQL wallet balance column type.
    dependencies = [
        ("wallet", "0002_wallet_created_at_alter_wallet_balance"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE wallet
                ALTER COLUMN balance TYPE numeric(12, 2)
                USING 0::numeric(12, 2);
            """,
            reverse_sql=migrations.RunSQL.noop,
            state_operations=[
                migrations.AlterField(
                    model_name="wallet",
                    name="balance",
                    field=models.DecimalField(
                        max_digits=12,
                        decimal_places=2,
                        default=0,
                    ),
                ),
            ],
        ),
    ]
