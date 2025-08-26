from django.contrib import admin
from .models import Outbound, WorkOrder, QualityCheck

@admin.register(Outbound)
class OutboundAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'out_time', 'librarian', 'taken_by', 'taken_at')
    list_filter = ('category', 'taken_by')
    search_fields = ('name', 'notes')

@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ('batch_no', 'title', 'operator', 'start_time', 'registered_at', 'registrar')
    search_fields = ('batch_no', 'title')
    readonly_fields = ('batch_no', 'start_time', 'operator')

@admin.register(QualityCheck)
class QualityCheckAdmin(admin.ModelAdmin):
    list_display = ('work_order', 'inspector', 'inspected_at', 'ocr_score', 'tiff_complete', 'jpeg_consistent', 'pdf_assembled', 'ocr_done', 'data_intact')
    list_filter = ('tiff_complete', 'jpeg_consistent', 'pdf_assembled', 'ocr_done', 'data_intact')
