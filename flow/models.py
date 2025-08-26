from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone

User = get_user_model()

class ProcessTemplate(models.Model):
    """
    流程模板。例：'纸本数字化-标准流程'
    """
    name = models.CharField("流程名称", max_length=100, unique=True, db_index=True)
    code = models.CharField("流程编码", max_length=50, unique=True)
    description = models.TextField("说明", blank=True, default="")
    # 预留：是否启用，版本等
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        verbose_name = "流程模板"
        verbose_name_plural = "流程模板"
        ordering = ["name"]

    def __str__(self):
        return self.name

class NodeTemplate(models.Model):
    """
    节点模板。MVP 仅支持线性：start -> approve -> end
    """
    NODE_TYPES = (
        ("start", "开始"),
        ("approve", "审批"),
        ("end", "结束"),
    )
    process = models.ForeignKey(ProcessTemplate, on_delete=models.CASCADE, related_name="nodes", verbose_name="所属流程")
    name = models.CharField("节点名称", max_length=100)
    code = models.CharField("节点编码", max_length=50)
    node_type = models.CharField("节点类型", max_length=20, choices=NODE_TYPES, default="approve")
    order = models.PositiveIntegerField("顺序", default=0)  # 线性流程用 order 控制

    # 指定处理人：MVP 先支持“固定到用户组或指定用户”二选一（后续可扩展到角色/动态）
    assigned_group_name = models.CharField("处理用户组名", max_length=100, blank=True, default="")
    assigned_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="指定用户")

    class Meta:
        verbose_name = "节点模板"
        verbose_name_plural = "节点模板"
        ordering = ["process", "order"]
        unique_together = ("process", "code")

    def __str__(self):
        return f"{self.process.name} - {self.name}"

class ProcessInstance(models.Model):
    """
    流程实例。一次从开始到结束的运行。
    """
    process = models.ForeignKey(ProcessTemplate, on_delete=models.PROTECT, related_name="instances", verbose_name="流程模板")
    starter = models.ForeignKey(User, on_delete=models.PROTECT, related_name="started_processes", verbose_name="发起人")
    start_time = models.DateTimeField("开始时间", default=timezone.now)
    end_time = models.DateTimeField("结束时间", null=True, blank=True)
    status = models.CharField("状态", max_length=20, default="running")  # running / finished / canceled
    current_node = models.ForeignKey('NodeInstance', null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="当前节点")

    class Meta:
        verbose_name = "流程实例"
        verbose_name_plural = "流程实例"

    def __str__(self):
        return f"{self.process.name}#{self.id}"

class NodeInstance(models.Model):
    """
    节点实例。记录当前到哪个节点、由谁处理。
    """
    process_instance = models.ForeignKey(ProcessInstance, on_delete=models.CASCADE, related_name="nodes", verbose_name="流程实例")
    node_template = models.ForeignKey(NodeTemplate, on_delete=models.PROTECT, verbose_name="节点模板")
    arrived_at = models.DateTimeField("到达时间", default=timezone.now)
    finished_at = models.DateTimeField("完成时间", null=True, blank=True)
    handler = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="handled_nodes", verbose_name="实际处理人")
    status = models.CharField("状态", max_length=20, default="pending")  # pending / done

    class Meta:
        verbose_name = "节点实例"
        verbose_name_plural = "节点实例"

    def __str__(self):
        return f"{self.process_instance} - {self.node_template.name}"

class Task(models.Model):
    """
    待办任务分配到用户。MVP：节点到达时，为对应用户或组内所有用户生成 Task。
    """
    node_instance = models.ForeignKey(NodeInstance, on_delete=models.CASCADE, related_name="tasks", verbose_name="节点实例")
    assignee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tasks", verbose_name="处理人")
    created_at = models.DateTimeField("创建时间", default=timezone.now)
    finished_at = models.DateTimeField("完成时间", null=True, blank=True)
    status = models.CharField("状态", max_length=20, default="open")  # open / closed

    class Meta:
        verbose_name = "任务"
        verbose_name_plural = "任务"
        indexes = [models.Index(fields=["assignee", "status"])]

    def __str__(self):
        return f"{self.assignee} - {self.node_instance}"

class Binding(models.Model):
    """
    将流程实例绑定到任意业务对象（如：出库单、数字化工作单、质检单等）。
    """
    process_instance = models.OneToOneField(ProcessInstance, on_delete=models.CASCADE, related_name="binding", verbose_name="流程实例")

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name="业务模型类型")
    object_id = models.PositiveIntegerField("业务对象ID")
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        verbose_name = "流程绑定"
        verbose_name_plural = "流程绑定"
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return f"{self.process_instance} -> {self.content_type}#{self.object_id}"
