from django.db import models
from django.conf import settings
import datetime

class Outbound(models.Model):
    CATEGORY_CHOICES = [
        ('book', '图书'),
        ('photo', '照片'),
        ('manuscript', '手稿'),
        ('other', '其它'),
    ]
    PLATEN_CHOICES = [
        ('flat', '平板'),
        ('vshape', 'V型板'),
    ]
    name = models.CharField("资料名称", max_length=100)
    category = models.CharField("资料种类", max_length=20, choices=CATEGORY_CHOICES)
    pages = models.IntegerField("页数", null=True, blank=True)
    platen = models.CharField("扫描设备", max_length=10, choices=PLATEN_CHOICES)
    color_paper = models.BooleanField("是否需要色纸", default=False)
    condition = models.TextField("出库书况登记", blank=True)
    notes = models.TextField("备注", blank=True)
    out_time = models.DateTimeField("出库时间", auto_now_add=True)
    librarian = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="登记人"
    )
    taken_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='taken_outbounds', verbose_name="承接人"
    )
    taken_at = models.DateTimeField("承接时间", null=True, blank=True)
    is_returned = models.BooleanField(default=False, verbose_name="是否已入库")
    returned_at = models.DateTimeField(null=True, blank=True, verbose_name="入库时间")

    def __str__(self):
        return f"{self.name} - {self.get_category_display()}"

class WorkOrder(models.Model):
    out_bound = models.OneToOneField(Outbound, on_delete=models.CASCADE, verbose_name="对应出库单")
    batch_no = models.CharField("批次号", max_length=12, unique=True)
    start_time = models.DateTimeField("数字化开始时间")
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="数字化负责人员"
    )
    title = models.CharField("题名信息", max_length=200)
    other_title = models.CharField("其它题名信息", max_length=200, blank=True)
    main_responsibility = models.CharField("主要责任者", max_length=100, blank=True)
    other_responsibility = models.CharField("其它责任者", max_length=100, blank=True)
    pub_place = models.CharField("出版地", max_length=100, blank=True)
    publisher = models.CharField("出版者", max_length=100, blank=True)
    pub_year = models.CharField("出版年", max_length=10, blank=True)
    total_pages = models.IntegerField("总页数")
    doc_type = models.CharField("文献类型标识", max_length=50, blank=True)
    registrar = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='registered_workorders', verbose_name="登记人员"
    )
    registered_at = models.DateTimeField("登记日期")
    notes = models.TextField("备注", blank=True)

    def __str__(self):
        return f"WorkOrder({self.batch_no}) - {self.title}"

class QualityCheck(models.Model):
    work_order = models.OneToOneField(WorkOrder, on_delete=models.CASCADE, verbose_name="对应工作单")
    tiff_complete = models.BooleanField("TIFF图片完整")
    jpeg_consistent = models.BooleanField("JPEG图片一致")
    pdf_assembled = models.BooleanField("是否合成PDF")
    ocr_done = models.BooleanField("是否完成OCR")
    ocr_score = models.IntegerField("OCR处理评分")
    data_intact = models.BooleanField("数据存储完整性")
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="检验人"
    )
    inspected_at = models.DateTimeField("检验时间", auto_now_add=True)

    def __str__(self):
        return f"QC for {self.work_order.batch_no}"

