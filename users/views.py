from django.shortcuts import render, redirect
from django.contrib.auth import login
from .models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model

User = get_user_model()


def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        emp_id = request.POST.get('emp_id')
        full_name = request.POST.get('full_name')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')

        # 工号重复校验
        if User.objects.filter(emp_id=emp_id).exists():
            return render(request, 'users/register.html', {'error': '该工号已被注册'})

        # 用户名重复校验
        if User.objects.filter(username=username).exists():
            return render(request, 'users/register.html', {'error': '该用户名已被注册'})

        # 密码一致性校验
        if password != password2:
            return render(request, 'users/register.html', {'error': '两次输入的密码不一致，请重新输入'})

        # 创建用户对象（会自动加密密码）
        user = User.objects.create_user(username=username, password=password, emp_id=emp_id)
        user.full_name = full_name
        user.save()

        # 自动登录并跳转到 dashboard
        login(request, user)
        return redirect('dashboard')

    return render(request, 'users/register.html')

from django.contrib.auth.models import Group
@login_required
def dashboard(request):
    user = request.user
    context = {
        'is_digital_staff': user.groups.filter(name='数字化室').exists(),
        'is_storage_staff': user.groups.filter(name='信息咨询室').exists(),
        'is_quality_staff': user.groups.filter(name='数字化室').exists(),
        "can_manage_attendance": request.user.has_perm("attendance.can_manage_attendance"),  # ✅ 传入模板
    }
    return render(request, 'users/dashboard.html', context)