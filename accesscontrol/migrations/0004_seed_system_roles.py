from django.db import migrations

# ROL-03: ship predefined system roles. These run inside every tenant schema
# (accesscontrol is a TENANT_APP), so each tenant gets its own copy. They are
# clonable but cannot be edited or deleted via the API.
SYSTEM_ROLES = [
    ("Administrator", "Full administrative access within the tenant."),
    ("Standard User", "Default access for ordinary staff users."),
]


def seed_roles(apps, schema_editor):
    Role = apps.get_model("accesscontrol", "Role")
    for name, description in SYSTEM_ROLES:
        Role.objects.get_or_create(
            name=name,
            defaults={
                "role_type": "system",
                "is_system": True,
                "description": description,
            },
        )


def unseed_roles(apps, schema_editor):
    Role = apps.get_model("accesscontrol", "Role")
    Role.objects.filter(name__in=[n for n, _ in SYSTEM_ROLES], is_system=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accesscontrol", "0003_role_userprofile"),
    ]

    operations = [
        migrations.RunPython(seed_roles, unseed_roles),
    ]
