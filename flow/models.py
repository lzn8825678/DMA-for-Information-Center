from __future__ import annotations
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator

User = settings.AUTH_USER_MODEL

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class FormSchema(TimeStampedModel):
    """动态表单：以 JSON Schema 存字段定义，UI Schema 做渲染提示。"""
    name = models.CharField(max_length=200, unique=True, verbose_name='表单名称')
    description = models.TextField(blank=True, verbose_name='说明')
    json_schema = models.JSONField(default=dict, verbose_name='JSON Schema')
    ui_schema = models.JSONField(default=dict, verbose_name='UI Schema')
    def __str__(self):
        return self.name

class FlowTemplate(TimeStampedModel):
    """流程模板：引用一个主表单，并定义节点拓扑。"""
    STATUS_CHOICES = (
        ('draft', '草稿'),
        ('active', '启用'),
        ('archived', '归档'),
    )
    code = models.SlugField(max_length=64, unique=True, verbose_name='模板编码')
    name = models.CharField(max_length=200, verbose_name='模板名称')
    description = models.TextField(blank=True, verbose_name='说明')
    form = models.ForeignKey(FormSchema, on_delete=models.PROTECT, related_name='flow_templates', verbose_name='主表单')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='draft', verbose_name='状态')
    version = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)], verbose_name='版本号')
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_flow_templates', verbose_name='创建人')


    class Meta:
        verbose_name = '流程模板'
        verbose_name_plural = '流程模板'


    def __str__(self):
        return f"{self.name} v{self.version}"

class NodeType(models.TextChoices):
    START = 'start', '开始'
    TASK = 'task', '任务'
    APPROVAL = 'approval', '审批'
    GATEWAY = 'gateway', '网关'
    END = 'end', '结束'

class FlowNode(TimeStampedModel):
    template = models.ForeignKey(FlowTemplate, on_delete=models.CASCADE, related_name='nodes', verbose_name='所属模板')
    code = models.SlugField(max_length=64, verbose_name='节点编码')
    name = models.CharField(max_length=200, verbose_name='节点名称')
    type = models.CharField(max_length=16, choices=NodeType.choices, default=NodeType.TASK, verbose_name='节点类型')
    assignees = models.JSONField(default=list, verbose_name='指派规则')
    """
    assignees 示例如下：
    [
        {"type":"user_ids", "value":[1,2]},
        {"type":"group_names", "value":["领导","数字化室"]},
        {"type":"by_field", "value":"applicant"} # 从表单值里取用户ID字段
    ]
    """
    allow_claim = models.BooleanField(default=False, verbose_name='是否抢单模式（组内认领）')
    form_overrides = models.JSONField(default=dict, verbose_name='表单覆盖/权限')
    """
    form_overrides: 控制本节点表单哪些字段可见/可编辑/必填
    {
        "readonly": ["fieldA"],
        "hidden": ["internal_note"],
        "required": ["approve_comment"]
    }
    """


class Meta:
    unique_together = ('template', 'code')
    ordering = ['id']
    verbose_name = '流程节点'
    verbose_name_plural = '流程节点'


    def __str__(self):
        return f"{self.template.code}:{self.code}-{self.name}"

class Transition(TimeStampedModel):
    template = models.ForeignKey(FlowTemplate, on_delete=models.CASCADE, related_name='transitions', verbose_name='所属模板')
    source = models.ForeignKey(FlowNode, on_delete=models.CASCADE, related_name='out_transitions', verbose_name='来源节点')
    target = models.ForeignKey(FlowNode, on_delete=models.CASCADE, related_name='in_transitions', verbose_name='目标节点')
    name = models.CharField(max_length=200, blank=True, verbose_name='流转名称')
    condition = models.TextField(blank=True, verbose_name='条件表达式')
    """
    condition：基于表单数据的布尔表达式，安全沙箱里 eval。
    例："form['ocr_score'] >= 90 and form['pages'] < 1000"
    空字符串代表无条件（默认直通）。
    """
    priority = models.IntegerField(default=100, verbose_name='优先级（数字越小越先匹配）')


    class Meta:
        ordering = ['priority', 'id']
        verbose_name = '流转边'
        verbose_name_plural = '流转边'


class InstanceStatus(models.TextChoices):
    RUNNING = 'running', '运行中'
    COMPLETED = 'completed', '已完成'
    TERMINATED = 'terminated', '已终止'


class FlowInstance(TimeStampedModel):
    template = models.ForeignKey(FlowTemplate, on_delete=models.PROTECT, related_name='instances', verbose_name='模板')
    status = models.CharField(max_length=16, choices=InstanceStatus.choices, default=InstanceStatus.RUNNING, verbose_name='状态')
    starter = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='started_instances', verbose_name='发起人')
    current_node = models.ForeignKey(FlowNode, on_delete=models.SET_NULL, null=True, blank=True, related_name='current_instances', verbose_name='当前节点')
    form_data = models.JSONField(default=dict, verbose_name='表单数据')
    title = models.CharField(max_length=255, blank=True, verbose_name='实例标题')


    class Meta:
        verbose_name = '流程实例'
        verbose_name_plural = '流程实例'


class WorkItemStatus(models.TextChoices):
    OPEN = 'open', '待处理'
    CLAIMED = 'claimed', '已认领'
    DONE = 'done', '已完成'
    CANCELED = 'canceled', '已取消'


class WorkItem(TimeStampedModel):
    instance = models.ForeignKey(FlowInstance, on_delete=models.CASCADE, related_name='work_items', verbose_name='所属实例')
    node = models.ForeignKey(FlowNode, on_delete=models.CASCADE, related_name='work_items', verbose_name='节点')
    assignees = models.JSONField(default=list, verbose_name='候选处理人')
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_work_items', verbose_name='当前处理人')
    status = models.CharField(max_length=16, choices=WorkItemStatus.choices, default=WorkItemStatus.OPEN, verbose_name='状态')
    due_at = models.DateTimeField(null=True, blank=True, verbose_name='到期时间')
    action = models.CharField(max_length=64, blank=True, verbose_name='处理动作')
    comment = models.TextField(blank=True, verbose_name='处理意见')


    class Meta:
        verbose_name = '待办/工作项'
        verbose_name_plural = '待办/工作项'


class ActionLog(TimeStampedModel):
    instance = models.ForeignKey(FlowInstance, on_delete=models.CASCADE, related_name='action_logs', verbose_name='实例')
    node = models.ForeignKey(FlowNode, on_delete=models.SET_NULL, null=True, verbose_name='节点')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='用户')
    action = models.CharField(max_length=64, verbose_name='动作')
    payload = models.JSONField(default=dict, verbose_name='载荷')
    remark = models.TextField(blank=True, verbose_name='备注')


    class Meta:
        verbose_name = '操作日志'
        verbose_name_plural = '操作日志'