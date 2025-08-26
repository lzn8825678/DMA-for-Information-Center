from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Department

# 定制UserAdmin以显示我们新增的字段
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'emp_id', 'full_name', 'department', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('emp_id', 'full_name', 'department')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('username', 'password1', 'password2', 'emp_id', 'full_name', 'department')}),
    )

admin.site.register(User, CustomUserAdmin)  # 注册自定义User模型:contentReference[oaicite:5]{index=5}
admin.site.register(Department)
