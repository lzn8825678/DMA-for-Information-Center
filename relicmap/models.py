from django.db import models
from django.conf import settings

class RelicLocation(models.Model):
    country = models.CharField("国家", max_length=100)
    region = models.CharField("地区", max_length=100, blank=True)
    institution = models.CharField("收藏机构", max_length=200)
    count = models.IntegerField("敦煌文物数量")
    digitized_percent = models.FloatField("数字化百分比", default=0)
    publication = models.TextField("相关出版物", blank=True)
    source = models.TextField("数据来源", blank=True)

    def __str__(self):
        return f"{self.country} - {self.institution}"

class RelicLog(models.Model):
    location = models.ForeignKey(RelicLocation, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    change_note = models.TextField("改动说明")
    change_reason = models.TextField("改动原因", blank=True)
    old_count = models.IntegerField("原数量")
    new_count = models.IntegerField("新数量")
    changed_at = models.DateTimeField("修改时间", auto_now_add=True)
