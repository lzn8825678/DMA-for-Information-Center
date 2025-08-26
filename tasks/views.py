from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Count
from django.contrib.auth.decorators import login_required

from Task_Django import settings
from .models import Task, Category

@login_required
def task_list(request):
    user = request.user

    # ✅ 查询任务：管理员看全部，普通用户看自己
    if user.is_superuser or user.is_staff:
        tasks = Task.objects.all()
    else:
        tasks = Task.objects.filter(responsible=user)

    # ✅ 分类统计图：仅统计已完成任务的分类分布
    category_stats = tasks.filter(is_done=True).values('categories__name').annotate(count=Count('id'))
    labels = []
    data = []
    for item in category_stats:
        name = item['categories__name'] or '未分类'
        count = item['count']
        if count > 0:
            labels.append(name)
            data.append(count)

    # ✅ 项目进度图：每个项目一个饼图，显示已完成 vs 未完成
    projects = Project.objects.all()
    project_charts = []
    for proj in projects:
        total = proj.task_set.count()
        done = proj.task_set.filter(is_done=True).count()
        if total == 0:
            continue
        project_charts.append({
            'name': proj.name,
            'done': done,
            'undone': total - done,
            'percent': round(done / total * 100, 1)
        })

    return render(request, 'tasks/task_list.html', {
        'tasks': tasks,
        'labels': labels,
        'data': data,
        'project_charts': project_charts,
    })

from django.utils import timezone
from .models import Task, Project, Category
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model

@login_required
def add_task(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        project_id = request.POST.get('project')
        category_ids = request.POST.getlist('categories')
        assignee_id = request.POST.get('responsible', None)
        User = get_user_model()
        # 确定任务负责人：若指定了他人则用指定用户，否则默认为当前用户
        if assignee_id:
            responsible_user = get_object_or_404(User, id=assignee_id)
        else:
            responsible_user = request.user
        project = get_object_or_404(Project, id=project_id)
        # 创建任务
        task = Task.objects.create(
            title=title,
            description=description,
            responsible=responsible_user,
            project=project,
            # is_done默认为False，created_at自动
        )
        # 添加分类多对多关系
        if category_ids:
            categories = Category.objects.filter(id__in=category_ids)
            task.categories.set(categories)
        return redirect('task_list')
    # GET 请求时，展示表单
    projects = Project.objects.all()
    categories = Category.objects.all()
    User = get_user_model()
    users = User.objects.all()
    return render(request, 'tasks/add_task.html', {
        'projects': projects,
        'categories': categories,
        'users': users
    })

from django.http import JsonResponse

@login_required
def complete_task(request, task_id):
    if request.method == 'POST':
        task = get_object_or_404(Task, id=task_id)
        # 权限检查：只有任务负责人本人或管理员可以标记完成
        if task.responsible != request.user and not request.user.is_staff:
            return JsonResponse({'error': '无权限标记该任务'}, status=403)
        if not task.is_done:
            task.is_done = True
            task.completed_at = timezone.now()
            task.save()
        return JsonResponse({'status': 'success'})
    else:
        # 非POST请求不允许
        return JsonResponse({'error': '必须使用POST请求'}, status=400)


from django.contrib.admin.views.decorators import staff_member_required
import csv
from django.http import HttpResponse
from datetime import datetime
from io import BytesIO

@login_required
def export_tasks(request):
    user = request.user

    # ✅ 查询任务范围
    if user.is_superuser or user.is_staff:
        tasks = Task.objects.select_related('project', 'responsible').all()
    else:
        tasks = Task.objects.select_related('project', 'responsible').filter(responsible=user)

    # ✅ 排序
    tasks = tasks.order_by('-is_done', '-completed_at')

    # ✅ 项目进度缓存
    project_stats = {}
    for proj in Project.objects.all():
        total = proj.task_set.count()
        done = proj.task_set.filter(is_done=True).count()
        progress = f"{(done / total * 100):.0f}%" if total > 0 else "0%"
        project_stats[proj.id] = progress

    # ✅ 文件名
    from datetime import datetime
    today_str = datetime.now().strftime("%Y%m%d")
    filename = f"任务报表_{today_str}.csv"

    # ✅ 使用带 BOM 的 UTF-8 编码（关键）
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')  # 写入 UTF-8 BOM

    writer = csv.writer(response)
    writer.writerow(["项目名称", "项目进度", "任务名称", "任务创建时间", "任务完成时间", "任务完成人", "任务耗时（小时）"])

    for task in tasks:
        proj = task.project
        proj_name = proj.name if proj else ""
        proj_progress = project_stats.get(proj.id, "") if proj else ""
        created_time = task.created_at.strftime("%Y-%m-%d %H:%M:%S")
        completed_time = task.completed_at.strftime("%Y-%m-%d %H:%M:%S") if task.completed_at else ""
        duration_hours = ""
        if task.completed_at:
            delta = task.completed_at - task.created_at
            duration_hours = f"{delta.total_seconds() // 3600}"

        writer.writerow([
            proj_name,
            proj_progress,
            task.title,
            created_time,
            completed_time,
            task.responsible.full_name,
            duration_hours
        ])

    return response

@login_required
def project_list(request):
    # 所有项目，按优先级排序（数值小的在前）
    projects = Project.objects.all().order_by('priority')
    return render(request, 'tasks/project_list.html', {'projects': projects})

@login_required
def project_detail(request, proj_id):
    project = get_object_or_404(Project, id=proj_id)
    user = request.user
    # 计算项目进度
    total_tasks = project.task_set.count()
    completed_tasks = project.task_set.filter(is_done=True).count()
    progress_percent = int(completed_tasks / total_tasks * 100) if total_tasks else 0

    # 决定任务可见范围：项目负责人或管理员可看该项目所有任务，否则仅看自己任务
    if user.is_superuser or user.is_staff or project.managers.filter(id=user.id).exists():
        tasks = project.task_set.select_related('responsible').all()
    else:
        tasks = project.task_set.select_related('responsible').filter(responsible=user)
    # 可按需要对tasks排序
    tasks = tasks.order_by('-created_at')

    # 准备饼图数据：已完成 vs 未完成
    chart_labels = ['已完成', '未完成']
    chart_data = [completed_tasks, total_tasks - completed_tasks]

    return render(request, 'tasks/project_detail.html', {
        'project': project,
        'tasks': tasks,
        'progress_percent': progress_percent,
        'chart_labels': chart_labels,
        'chart_data': chart_data
    })
