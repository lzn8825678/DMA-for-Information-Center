from django.shortcuts import render, get_object_or_404, redirect
from .models import RelicLocation, RelicLog
from django.contrib.auth.decorators import login_required
from collections import defaultdict

@login_required
@login_required
def relic_dashboard(request):
    locations = RelicLocation.objects.all().order_by('country', 'region', 'institution')
    raw_tree = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))

    for loc in locations:
        pubs = loc.publication.strip().split('\n') if loc.publication else []
        raw_tree[loc.country][loc.region][loc.institution] = {
            'count': loc.count,
            'digitized_percent': loc.digitized_percent,
            'publications': pubs,
            'source': loc.source,
            'id': loc.id,
        }

    # 转成普通 dict（递归）
    def deep_convert(d):
        if isinstance(d, defaultdict):
            d = {k: deep_convert(v) for k, v in d.items()}
        return d

    tree = deep_convert(raw_tree)

    return render(request, 'relicmap/dashboard.html', {'tree': tree})

@login_required
def relic_detail(request, pk):
    location = get_object_or_404(RelicLocation, id=pk)
    return render(request, 'relicmap/detail.html', {'location': location})

@login_required
def relic_logs(request, pk):
    location = get_object_or_404(RelicLocation, id=pk)
    logs = RelicLog.objects.filter(location=location).order_by('-changed_at')
    return render(request, 'relicmap/logs.html', {'location': location, 'logs': logs})

from .forms import RelicLocationForm
from django.contrib import messages

@login_required
def add_location(request):
    if request.method == 'POST':
        form = RelicLocationForm(request.POST)
        if form.is_valid():
            loc = form.save()
            messages.success(request, '✅ 添加成功')
            return redirect('relic_dashboard')
    else:
        form = RelicLocationForm()
    return render(request, 'relicmap/add.html', {'form': form})