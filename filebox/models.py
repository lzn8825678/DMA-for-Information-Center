from django.db import models
from django.conf import settings

class FileCategory(models.Model):
    name = models.CharField("分类名称", max_length=50)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children', on_delete=models.CASCADE)

    class Meta:
        verbose_name = "文件分类"
        verbose_name_plural = "文件分类"

    def __str__(self):
        return self.name

class UploadedFile(models.Model):
    title = models.CharField("文件标题", max_length=100)
    file = models.FileField("上传文件", upload_to='uploads/')
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(FileCategory, on_delete=models.SET_NULL, null=True, verbose_name="所属分类")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name="上传者")
    uploaded_at = models.DateTimeField("上传时间", auto_now_add=True)

    def __str__(self):
        return self.title
