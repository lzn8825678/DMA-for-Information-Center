from django.contrib import admin
from .models import RelicLocation, RelicLog

@admin.register(RelicLocation)
class RelicLocationAdmin(admin.ModelAdmin):
    list_display = ('country', 'region', 'institution', 'count', 'digitized_percent')

@admin.register(RelicLog)
class RelicLogAdmin(admin.ModelAdmin):
    list_display = ('location', 'user', 'old_count', 'new_count', 'changed_at')
