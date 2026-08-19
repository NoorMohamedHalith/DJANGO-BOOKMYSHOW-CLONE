from django.shortcuts import render
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from .services import AnalyticsService


def check_staff_permission(request):
    return request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)


@login_required(login_url='/login/')
def dashboard_view(request):
    if not check_staff_permission(request):
        return HttpResponseForbidden("Admin access required to view the Analytics Dashboard.")

    kpis = AnalyticsService.get_kpi_summary()
    context = {
        'kpis': kpis
    }
    return render(request, 'analytics/dashboard.html', context)


@login_required(login_url='/login/')
def api_kpi_summary(request):
    if not check_staff_permission(request):
        return JsonResponse({'error': 'Staff permission required'}, status=403)
    kpis = AnalyticsService.get_kpi_summary()
    return JsonResponse({'success': True, 'kpis': kpis})


@login_required(login_url='/login/')
def api_revenue_timeline(request):
    if not check_staff_permission(request):
        return JsonResponse({'error': 'Staff permission required'}, status=403)
    period = request.GET.get('period', '7d')
    data = AnalyticsService.get_revenue_timeline(period=period)
    return JsonResponse({'success': True, **data})


@login_required(login_url='/login/')
def api_top_movies(request):
    if not check_staff_permission(request):
        return JsonResponse({'error': 'Staff permission required'}, status=403)
    data = AnalyticsService.get_top_performing_movies()
    return JsonResponse({'success': True, **data})


@login_required(login_url='/login/')
def api_theater_occupancy(request):
    if not check_staff_permission(request):
        return JsonResponse({'error': 'Staff permission required'}, status=403)
    data = AnalyticsService.get_theater_occupancy_rates()
    return JsonResponse({'success': True, **data})


@login_required(login_url='/login/')
def api_user_growth(request):
    if not check_staff_permission(request):
        return JsonResponse({'error': 'Staff permission required'}, status=403)
    data = AnalyticsService.get_user_growth_timeline()
    return JsonResponse({'success': True, **data})


@login_required(login_url='/login/')
def export_csv_report_view(request):
    if not check_staff_permission(request):
        return HttpResponseForbidden("Staff permission required to export reports.")

    report_type = request.GET.get('type', 'sales').lower()
    if report_type not in ['sales', 'bookings', 'movies']:
        report_type = 'sales'

    csv_content = AnalyticsService.generate_csv_report(report_type=report_type)

    response = HttpResponse(csv_content, content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="analytics_{report_type}_report.csv"'
    return response
