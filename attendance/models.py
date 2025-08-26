from django.db import models
from django.conf import settings

class AttendanceRecord(models.Model):
    TYPE_CHOICES = [('leave', '请假'), ('overtime', '加班')]
    LEAVE_TYPE_CHOICES = [('sick', '病假'), ('personal', '事假'), ('annual', '年假'), ('other', '其它')]

    type = models.CharField("类型", choices=TYPE_CHOICES, max_length=10)
    person_name = models.CharField("请假人员 / 加班人员", max_length=50, default="未知人员")
    registrar = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='registered_attendance', verbose_name="登记人")
    # user_name = models.CharField("请假/加班人员", max_length=100, default='未知人员')
    # person_name = models.CharField("请假/加班人员", max_length=100, default="未知人员")
    start_date = models.DateField("开始时间")
    duration = models.FloatField("时长", help_text="请假单位为天，加班单位为小时")

    leave_type = models.CharField("请假类型", max_length=20, choices=LEAVE_TYPE_CHOICES, blank=True)
    leave_reason = models.TextField("请假事由", blank=True)

    overtime_reason = models.TextField("加班事由", blank=True)
    overtime_place = models.CharField("加班地点", max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [
            ("can_manage_attendance", "可管理考勤记录"),
        ]

    def __str__(self):
        return f"{self.get_type_display()} - {self.person_name} - {self.start_date}"