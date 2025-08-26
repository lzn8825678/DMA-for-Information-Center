# tasks/models.py
from django.db import models

from Task_Django import settings


class Category(models.Model):
    name = models.CharField("分类名称", max_length=20)

    def __str__(self):
        return self.name

class Project(models.Model):
    name = models.CharField("项目名称", max_length=100)
    priority = models.IntegerField("优先级", default=0)
    managers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, verbose_name="项目负责人"
    )

    def __str__(self):
        return self.name

from django.conf import settings
from digitization.models import Outbound

class Task(models.Model):
    title = models.CharField("任务名称", max_length=100)
    description = models.TextField("描述", blank=True)
    is_done = models.BooleanField("已完成？", default=False)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    completed_at = models.DateTimeField("完成时间", null=True, blank=True)
    out_bound = models.ForeignKey(Outbound, null=True, blank=True, on_delete=models.SET_NULL)
    # 任务负责人（执行人）
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        verbose_name="负责人"
    )
    # 任务所属项目
    project = models.ForeignKey(Project, on_delete=models.CASCADE, verbose_name="所属项目")
    # 任务分类（多选多对多）
    categories = models.ManyToManyField(Category, blank=True, verbose_name="分类")

    def __str__(self):
        return self.title
