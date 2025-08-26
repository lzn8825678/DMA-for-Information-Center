from django.contrib import admin
from .models import FileCategory, UploadedFile

admin.site.register(FileCategory)
admin.site.register(UploadedFile)
