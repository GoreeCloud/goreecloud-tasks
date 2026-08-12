"""Administrative account controls.

Task and project content is intentionally not registered in Django admin. An
application administrator can manage accounts without receiving a convenient
normal-interface browser for another user's private task content.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class GoreeCloudUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("GoreeCloud Tasks", {"fields": ("display_name", "timezone")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("GoreeCloud Tasks", {"fields": ("display_name", "timezone")}),
    )
