from django.contrib import admin
from .models import Task, Project, Category

class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'responsible', 'is_done', 'created_at', 'completed_at')
    list_filter = ('project', 'is_done', 'categories')
    search_fields = ('title', 'description')

admin.site.register(Task, TaskAdmin)
admin.site.register(Project)
admin.site.register(Category)

class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'priority')
    list_editable = ('priority',)
    filter_horizontal = ('managers',)

admin.site.unregister(Project)
admin.site.register(Project, ProjectAdmin)