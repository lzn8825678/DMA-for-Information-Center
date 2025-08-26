from django.contrib import admin
from .models import AttendanceRecord

@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ('type', 'person_name', 'start_date', 'duration', 'registrar', 'created_at')
    list_filter = ('type', 'start_date', 'registrar')
    search_fields = ('person_name', 'leave_reason', 'overtime_reason')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'registrar')  # 可选，控制只读字段

    # ✅ 限制权限：仅超级管理员可修改/删除
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
