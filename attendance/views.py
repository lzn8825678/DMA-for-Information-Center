from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, permission_required
from .models import AttendanceRecord
from .forms import AttendanceForm
from django.db.models import Sum
from calendar import monthrange
from datetime import date
from .models import AttendanceRecord
from django.contrib.auth import get_user_model
User = get_user_model()
@login_required
@permission_required('attendance.can_manage_attendance', raise_exception=True)
def attendance_list(request):
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))

    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])

    records = AttendanceRecord.objects.filter(
        start_date__gte=start_date,
        start_date__lte=end_date
    ).order_by('-created_at')

    leave_data = records.filter(type='leave').values('person_name').annotate(total=Sum('duration'))
    overtime_data = records.filter(type='overtime').values('person_name').annotate(total=Sum('duration'))
    leave_labels = [r['person_name'] for r in leave_data]
    leave_values = [r['total'] for r in leave_data]
    overtime_labels = [r['person_name'] for r in overtime_data]
    overtime_values = [r['total'] for r in overtime_data]

    return render(request, 'attendance/attendance_list.html', {
        'records': records,
        'year': year,
        'month': month,
        'leave_labels': leave_labels,
        'leave_values': leave_values,
        'overtime_labels': overtime_labels,
        'overtime_values': overtime_values,
    })

from django.contrib import messages
@login_required
@permission_required('attendance.can_manage_attendance', raise_exception=True)
def attendance_add(request):
    if request.method == 'POST':
        form = AttendanceForm(request.POST)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.user_name = form.cleaned_data['person_name']
            instance.registrar = request.user
            instance.save()
            messages.success(request, "考勤记录添加成功！")
            return redirect('attendance_list')
    else:
        form = AttendanceForm()

    return render(request, 'attendance/attendance_add.html', {'form': form})


import csv
from django.http import HttpResponse
from django.utils import timezone


@permission_required('attendance.can_manage_attendance', raise_exception=True)
def export_attendance_csv(request):
    now_str = timezone.now().strftime('%Y%m%d')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_report_{now_str}.csv"'
    response.write('\ufeff')  # 防止中文乱码，写入 UTF-8 BOM

    writer = csv.writer(response)
    writer.writerow([
        "类型", "记录人员", "开始时间", "结束时间", "时长",
        "请假类型", "请假事由", "加班地点", "加班事由",
        "登记人", "登记时间"
    ])

    records = AttendanceRecord.objects.select_related('user', 'registrar').order_by('-created_at')

    for r in records:
        writer.writerow([
            r.get_type_display(),
            r.person_name,
            r.start_date,
            r.end_date,
            r.duration,
            r.get_leave_type_display() if r.type == 'leave' else '',
            r.leave_reason if r.type == 'leave' else '',
            r.overtime_place if r.type == 'overtime' else '',
            r.overtime_reason if r.type == 'overtime' else '',
            r.registrar.full_name,
            r.created_at.strftime('%Y-%m-%d %H:%M'),
        ])

    return response