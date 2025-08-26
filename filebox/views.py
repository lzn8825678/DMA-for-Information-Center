from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import UploadedFile, FileCategory
from django.core.files.storage import FileSystemStorage
import zipfile
import io
from django.core.files.base import ContentFile
from django.contrib import messages
@login_required
def upload_file(request):
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category')
        category = FileCategory.objects.filter(id=category_id).first() if category_id else None

        files = request.FILES.getlist('file')
        if not files:
            return render(request, 'filebox/upload.html', {
                'categories': FileCategory.objects.all(),
                'error': '请选择至少一个文件'
            })

        normal_file_counter = 1  # 用于多文件编号

        for file in files:
            # ✅ ZIP 文件解压上传
            if file.name.endswith('.zip'):
                with zipfile.ZipFile(file) as zf:
                    for name in zf.namelist():
                        if name.endswith('/') or name.startswith('__MACOSX') or name.endswith('.DS_Store'):
                            continue
                        try:
                            filename = name.encode('cp437').decode('gbk')
                        except UnicodeDecodeError:
                            filename = name
                        data = zf.read(name)
                        if not data:
                            continue
                        zip_title = f"{title}_{filename}" if title else filename
                        UploadedFile.objects.create(
                            title=zip_title,
                            description=description,
                            file=ContentFile(data, name=filename),
                            category=category,
                            uploaded_by=request.user
                        )
            else:
                # ✅ 普通上传支持多文件+编号
                if title:
                    actual_title = f"{title}_{normal_file_counter}"
                else:
                    actual_title = file.name
                normal_file_counter += 1

                UploadedFile.objects.create(
                    title=actual_title,
                    description=description,
                    file=file,
                    category=category,
                    uploaded_by=request.user
                )

        messages.success(request, "✅ 文件上传成功！")
        return redirect('file_list')

    return render(request, 'filebox/upload.html', {
        'categories': FileCategory.objects.all()
    })


from django.core.paginator import Paginator
from collections import defaultdict
import json
@login_required
def file_list(request):
    categories = FileCategory.objects.select_related('parent').all()
    query = request.GET.get('q', '').strip()
    selected_category_id = request.GET.get('category')

    files = UploadedFile.objects.all().select_related('category', 'uploaded_by')
    if query:
        files = files.filter(title__icontains=query)
    if selected_category_id:
        files = files.filter(category__id=selected_category_id)

    # ✅ 构建树形数据（供 jstree 使用）
    category_tree = []
    for cat in categories:
        category_tree.append({
            "id": str(cat.id),
            "parent": str(cat.parent.id) if cat.parent else "#",
            "text": cat.name,
            "a_attr": {"href": f"?category={cat.id}"}
        })

    # 分类分组展示
    from collections import defaultdict
    grouped_files = defaultdict(list)
    for f in files:
        grouped_files[f.category.name if f.category else "未分类"].append(f)

    return render(request, 'filebox/tree_list.html', {
        'grouped_files': dict(grouped_files),
        'categories': categories,
        'category_tree_json': json.dumps(category_tree, ensure_ascii=False),  # ✅ 传入模板
        'query': query,
        'selected_category_id': selected_category_id,
    })


from django.http import HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404

@require_POST
@login_required
def delete_file(request, file_id):
    file = get_object_or_404(UploadedFile, id=file_id)

    if file.uploaded_by != request.user and not request.user.is_superuser:
        return HttpResponseForbidden("无权限删除该文件")

    file.file.delete()  # 删除物理文件
    file.delete()       # 删除数据库记录
    return redirect('file_list')

from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def manage_categories(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            FileCategory.objects.create(name=name)
            return redirect('manage_categories')

    categories = FileCategory.objects.all()
    return render(request, 'filebox/manage_categories.html', {
        'categories': categories
    })

@staff_member_required
@require_POST
def delete_category(request, category_id):
    category = get_object_or_404(FileCategory, id=category_id)
    category.delete()
    return redirect('manage_categories')