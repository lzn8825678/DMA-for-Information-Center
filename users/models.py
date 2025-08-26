# users/models.py
from django.db import models
from django.conf import settings

class Department(models.Model):
    name = models.CharField("科室名称", max_length=50, unique=True)
    leader = models.ForeignKey(
        'users.User',  #修改为字符串引用
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='led_departments',  #添加 related_name 解决反向冲突
        verbose_name="负责人"
    )

    def __str__(self):
        return self.name

from django.contrib.auth.models import AbstractUser, User


class User(AbstractUser):
    emp_id = models.CharField("工号", max_length=20, unique=True)
    full_name = models.CharField("姓名", max_length=30)
    department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="所属科室"
    )

    def __str__(self):
        # 返回显示姓名和工号，方便识别
        return f"{self.full_name}({self.emp_id})"
