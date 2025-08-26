from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Outbound, WorkOrder, QualityCheck


def is_librarian(user):
    # 简单假设属于某组为库管，否则用管理员权限
    return user.is_staff or user.groups.filter(name="信息咨询室").exists()

@login_required
@user_passes_test(is_librarian)
def add_outbound(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        category = request.POST.get('category')
        pages = request.POST.get('pages') or None
        platen = request.POST.get('platen')
        color_paper = (request.POST.get('color_paper') == 'on')
        condition = request.POST.get('condition', '')
        notes = request.POST.get('notes', '')
        # 创建出库单
        Outbound.objects.create(
            name=name, category=category, pages=pages if pages else None,
            platen=platen, color_paper=color_paper,
            condition=condition, notes=notes,
            librarian=request.user
        )
        return redirect('outbound_list')
    # GET请求，展示表单
    return render(request, 'digitization/add_outbound.html')

@login_required
def outbound_list(request):
    # 查询未被承接的出库单
    out_list = Outbound.objects.filter(taken_by__isnull=True)
    return render(request, 'digitization/outbound_list.html', {'out_list': out_list})


from tasks.models import Task, Project, Category
@login_required
def claim_outbound(request, out_id):
    project = Project.objects.filter(name="馆藏纸本资源数字化").first()
    if not project:
        return HttpResponse("⚠️ 请先创建项目：馆藏纸本资源数字化")

    out_bound = get_object_or_404(Outbound, id=out_id)
    category = Category.objects.filter(name="扫描").first()
    if not category:
        return HttpResponse("⚠️ 请先创建分类：扫描")

    # 防止重复承接
    if out_bound.taken_by or out_bound.taken_at:
        return redirect('outbound_list')

    # 防止登记人自己承接
    if out_bound.librarian_id == request.user.id:
        return redirect('outbound_list')

    # 执行承接
    out_bound.taken_by = request.user
    out_bound.taken_at = timezone.now()
    out_bound.save()

    # ➤ 生成批次号（日期+当日序号）
    date_str = out_bound.taken_at.strftime("%Y%m%d")
    today_count = WorkOrder.objects.filter(batch_no__startswith=date_str).count() + 1
    batch_no = f"{date_str}{today_count:04d}"

    # ➤ 创建数字化工作单
    work_order = WorkOrder.objects.create(
        out_bound=out_bound,
        batch_no=batch_no,
        start_time=out_bound.taken_at,
        operator=request.user,
        title="",  # 待填写
        main_responsibility="", other_responsibility="",
        other_title="", pub_place="", publisher="", pub_year="",
        total_pages=0, doc_type="",
        registrar=request.user,
        registered_at=out_bound.taken_at
    )

    # ➤ 创建任务（描述 = 批次号数字化）
    task = Task.objects.create(
        title="馆藏纸本资源数字化",
        description=f"{batch_no}数字化",
        responsible=request.user,
        project=project,
        out_bound=out_bound,
    )
    task.categories.add(category)

    # 跳转至填写页面
    return redirect('edit_workorder', out_id)


from .models import WorkOrder

@login_required
def edit_workorder(request, out_id):
    work_order = get_object_or_404(WorkOrder, out_bound__id=out_id)
    # 权限：只有该工作单的操作人员(承接人)或管理员能编辑
    if work_order.operator_id != request.user.id and not request.user.is_staff:
        return redirect('outbound_list')
    if request.method == 'POST':
        # 获取表单数据
        work_order.title = request.POST.get('title', '')
        work_order.other_title = request.POST.get('other_title', '')
        work_order.main_responsibility = request.POST.get('main_responsibility', '')
        work_order.other_responsibility = request.POST.get('other_responsibility', '')
        work_order.pub_place = request.POST.get('pub_place', '')
        work_order.publisher = request.POST.get('publisher', '')
        work_order.pub_year = request.POST.get('pub_year', '')
        work_order.total_pages = int(request.POST.get('total_pages') or 0)
        work_order.doc_type = request.POST.get('doc_type', '')
        work_order.notes = request.POST.get('notes', '')
        work_order.registrar = request.user
        work_order.registered_at = timezone.now()
        work_order.save()
        return redirect('outbound_list')
    # GET: 显示表单，初始值为当前记录值
    return render(request, 'digitization/edit_workorder.html', {'wo': work_order})

@login_required
def pending_quality_list(request):
    # 查询所有未检验且已登记完成的工作单
    workorders = WorkOrder.objects.filter(qualitycheck__isnull=True).filter(title__gt="").select_related('out_bound')
    # 过滤条件解释：qualitycheck__isnull=True确保没有对应检验；title__gt="" 确保题名已填写（用于排除尚未登记完成的）
    return render(request, 'digitization/pending_quality_list.html', {'workorders': workorders})

@login_required
def check_quality(request, wo_id):
    work_order = get_object_or_404(WorkOrder, id=wo_id)
    # 防止承接人自己检验
    if work_order.operator_id == request.user.id:
        return redirect('pending_quality_list')
    # 若已经有检验记录也不应重复
    if hasattr(work_order, 'qualitycheck'):
        return redirect('pending_quality_list')
    if request.method == 'POST':
        # 获取各选项值，checkbox未选不会出现在POST，需要默认False
        tiff_complete = True if request.POST.get('tiff_complete') == 'on' else False
        jpeg_consistent = True if request.POST.get('jpeg_consistent') == 'on' else False
        pdf_assembled = True if request.POST.get('pdf_assembled') == 'on' else False
        ocr_done = True if request.POST.get('ocr_done') == 'on' else False
        ocr_score = int(request.POST.get('ocr_score') or 0)
        data_intact = True if request.POST.get('data_intact') == 'on' else False
        # 创建质检记录
        qc = QualityCheck.objects.create(
            work_order=work_order,
            tiff_complete=tiff_complete,
            jpeg_consistent=jpeg_consistent,
            pdf_assembled=pdf_assembled,
            ocr_done=ocr_done,
            ocr_score=ocr_score,
            data_intact=data_intact,
            inspector=request.user
        )
        # 标记任务完成：通过出库单找到关联任务
        Task.objects.filter(out_bound=work_order.out_bound).update(is_done=True, completed_at=timezone.now())
        return redirect('pending_quality_list')
    # GET: 展示检验表单
    return render(request, 'digitization/check_quality.html', {'wo': work_order})

import csv
@login_required
def export_full_report(request):
    # 只允许管理员导出
    if not request.user.is_staff:
        return HttpResponse("无权限访问", status=403)

    # 创建响应对象，设置 CSV 导出 headers
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="数字化工作总报表.csv"'
    response.write('\ufeff')  # 添加 BOM 防止中文乱码

    writer = csv.writer(response)
    writer.writerow([
        "资料名称", "资料种类", "页数", "扫描设备", "色纸需求", "出库书况", "备注",
        "登记人", "出库时间", "承接人", "承接时间",
        "批次号", "题名", "其它题名", "主要责任者", "其它责任者", "出版地", "出版者", "出版年",
        "总页数", "文献类型标识", "登记人员", "登记日期", "工作单备注",
        "TIFF图片完整", "JPEG一致", "PDF合成", "OCR完成", "OCR评分", "数据完整性", "检验人", "检验时间"
    ])

    outbounds = Outbound.objects.all().select_related('librarian', 'taken_by')

    for outbound in outbounds:
        workorder = getattr(outbound, 'workorder', None)
        qc = getattr(workorder, 'qualitycheck', None) if workorder else None

        writer.writerow([
            outbound.name,
            outbound.get_category_display(),
            outbound.pages,
            outbound.get_platen_display(),
            '是' if outbound.color_paper else '否',
            outbound.condition,
            outbound.notes,
            outbound.librarian.full_name if outbound.librarian else '',
            outbound.out_time.strftime('%Y-%m-%d %H:%M') if outbound.out_time else '',
            outbound.taken_by.full_name if outbound.taken_by else '',
            outbound.taken_at.strftime('%Y-%m-%d %H:%M') if outbound.taken_at else '',
            workorder.batch_no if workorder else '',
            workorder.title if workorder else '',
            workorder.other_title if workorder else '',
            workorder.main_responsibility if workorder else '',
            workorder.other_responsibility if workorder else '',
            workorder.pub_place if workorder else '',
            workorder.publisher if workorder else '',
            workorder.pub_year if workorder else '',
            workorder.total_pages if workorder else '',
            workorder.doc_type if workorder else '',
            workorder.registrar.full_name if workorder and workorder.registrar else '',
            workorder.registered_at.strftime('%Y-%m-%d %H:%M') if workorder and workorder.registered_at else '',
            workorder.notes if workorder else '',
            '是' if qc and qc.tiff_complete else '否',
            '是' if qc and qc.jpeg_consistent else '否',
            '是' if qc and qc.pdf_assembled else '否',
            '是' if qc and qc.ocr_done else '否',
            qc.ocr_score if qc else '',
            '是' if qc and qc.data_intact else '否',
            qc.inspector.full_name if qc and qc.inspector else '',
            qc.inspected_at.strftime('%Y-%m-%d %H:%M') if qc and qc.inspected_at else ''
        ])

    return response


@login_required
def return_list(request):
    """展示当前用户负责的可入库出库单"""
    outbounds = Outbound.objects.filter(
        librarian=request.user,
        taken_by__isnull=False,
        workorder__isnull=False,
        workorder__qualitycheck__isnull=False,
        is_returned=False
    ).select_related('workorder__qualitycheck', 'taken_by')

    return render(request, 'digitization/return_list.html', {
        'records': outbounds
    })


@login_required
def confirm_return(request, out_id):
    outbound = get_object_or_404(Outbound, id=out_id)

    if outbound.librarian_id != request.user.id:
        return HttpResponse("⚠️ 只有最初出库人可以入库。", status=403)

    if outbound.is_returned:
        return redirect('return_list')

    outbound.is_returned = True
    outbound.returned_at = timezone.now()
    outbound.save()

    return redirect('return_list')



from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone

@login_required
def returned_list(request):
    """展示所有已完成入库的资料记录"""
    records = Outbound.objects.filter(
        is_returned=True,
        workorder__isnull=False,
        workorder__qualitycheck__isnull=False
    ).select_related('librarian', 'taken_by', 'workorder__qualitycheck')

    return render(request, 'digitization/returned_list.html', {
        'records': records
    })

@login_required
def export_returned_csv(request):
    if not request.user.is_authenticated:
        return HttpResponse("未授权", status=403)

    now_str = timezone.now().strftime('%Y%m%d_%H%M')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="入库记录导出_{now_str}.csv"'
    response.write('\ufeff')  # BOM for Excel

    writer = csv.writer(response)
    writer.writerow([
        "资料名称", "资料种类", "页数", "扫描设备", "色纸需求", "出库书况", "出库备注",
        "出库登记人", "出库时间", "承接人", "承接时间",
        "批次号", "题名", "其它题名", "主要责任者", "其它责任者",
        "出版地", "出版者", "出版年", "总页数", "文献类型标识",
        "工作单登记人", "登记时间", "工作备注",
        "TIFF完整", "JPEG一致", "PDF合成", "OCR完成", "OCR评分", "数据完整性", "质检人", "检验时间",
        "是否已入库", "入库时间"
    ])

    outbounds = Outbound.objects.filter(
        is_returned=True,
        workorder__isnull=False,
        workorder__qualitycheck__isnull=False
    ).select_related(
        'librarian', 'taken_by', 'workorder__registrar', 'workorder__qualitycheck__inspector'
    )

    for obj in outbounds:
        wo = obj.workorder
        qc = wo.qualitycheck

        writer.writerow([
            obj.name,
            obj.get_category_display(),
            obj.pages or '',
            obj.get_platen_display(),
            '是' if obj.color_paper else '否',
            obj.condition,
            obj.notes,
            obj.librarian.full_name if obj.librarian else '',
            obj.out_time.strftime('%Y-%m-%d %H:%M') if obj.out_time else '',
            obj.taken_by.full_name if obj.taken_by else '',
            obj.taken_at.strftime('%Y-%m-%d %H:%M') if obj.taken_at else '',

            wo.batch_no,
            wo.title,
            wo.other_title,
            wo.main_responsibility,
            wo.other_responsibility,
            wo.pub_place,
            wo.publisher,
            wo.pub_year,
            wo.total_pages,
            wo.doc_type,
            wo.registrar.full_name if wo.registrar else '',
            wo.registered_at.strftime('%Y-%m-%d %H:%M') if wo.registered_at else '',
            wo.notes,

            '是' if qc.tiff_complete else '否',
            '是' if qc.jpeg_consistent else '否',
            '是' if qc.pdf_assembled else '否',
            '是' if qc.ocr_done else '否',
            qc.ocr_score,
            '是' if qc.data_intact else '否',
            qc.inspector.full_name if qc.inspector else '',
            qc.inspected_at.strftime('%Y-%m-%d %H:%M') if qc.inspected_at else '',

            '是',
            obj.returned_at.strftime('%Y-%m-%d %H:%M') if obj.returned_at else '',
        ])

    return response

@login_required
def return_detail(request, out_id):
    outbound = get_object_or_404(Outbound, id=out_id)

    if not outbound.is_returned:
        return HttpResponse("⚠️ 尚未入库的记录无法查看详情。", status=403)

    workorder = getattr(outbound, 'workorder', None)
    qc = getattr(workorder, 'qualitycheck', None) if workorder else None

    return render(request, 'digitization/return_detail.html', {
        'outbound': outbound,
        'workorder': workorder,
        'qc': qc,
    })
