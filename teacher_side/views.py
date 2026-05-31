import csv
import io
import json

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST
import pandas as pd

from teacher_side.matcher.genetic_matcher import match
from teacher_side.matcher.utils import get_weights
from .forms import UploadFileForm
from .models import CSVGeneration


@staff_member_required
def teacher_dashboard(request):
    generations = CSVGeneration.objects.order_by('-generated_at')[:10]
    return render(request, 'teammatcher/teacher_dashboard.html', {
        'generations': generations
    })


@staff_member_required
@require_GET
def dashboard_api_load(request):
    """
    GET /teacher/dashboard/api/load/?generation_id=ID
    Parses the CSV from a CSVGeneration and returns teams grouped by 'cp' column.
    Response: { teams: [{name, members:[username,…]}, …], max_size: int }
    """
    gen_id = request.GET.get("generation_id")
    if not gen_id:
        return JsonResponse({"error": "generation_id required"}, status=400)

    try:
        generation = CSVGeneration.objects.get(pk=gen_id)
    except CSVGeneration.DoesNotExist:
        return JsonResponse({"error": "Generation not found"}, status=404)

    reader = csv.DictReader(io.StringIO(generation.csv_data))
    rows   = list(reader)

    if not rows:
        return JsonResponse({"error": "CSV is empty"}, status=400)

    if "cp" not in rows[0]:
        return JsonResponse({"error": "CSV has no 'cp' column"}, status=400)

    teams_dict = {}
    for row in rows:
        team_name = row.get("cp", "").strip()
        username  = row.get("username", "").strip()
        if not team_name or not username:
            continue
        teams_dict.setdefault(team_name, []).append(username)

    teams = [{"name": name, "members": members}
             for name, members in sorted(teams_dict.items())]

    return JsonResponse({
        "teams":    teams,
        "max_size": generation.team_size + 1,
    })


@staff_member_required
@require_POST
def dashboard_api_export(request):
    """
    POST /teacher/dashboard/api/export/
    Body: { generation_id: int, teams: [{name, members:[…]}, …] }
    Returns a CSV file in LMS format: username, external_user_id, mode, cp, wp
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse("Invalid JSON", status=400)

    gen_id = body.get("generation_id")
    teams  = body.get("teams", [])

    if not gen_id or not teams:
        return HttpResponse("generation_id and teams are required", status=400)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["username", "external_user_id", "mode", "cp", "wp"])

    for team in teams:
        team_name = team.get("name", "")
        for username in team.get("members", []):
            writer.writerow([username, "", "professional", team_name, team_name])

    filename = f"teams_adjusted_{gen_id}.csv"
    return HttpResponse(
        output.getvalue(),
        content_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@staff_member_required
def index(request):
    teams = []

    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            # get data from form
            df = pd.read_csv(request.FILES['file'])
            df = df.dropna(how='all')

            team_template = form.cleaned_data.get('team_template')
            weights = get_weights(form)
            constraints = {
                'min_size': form.cleaned_data['min_team_size'],
                'max_size': form.cleaned_data['max_team_size'],
            }

            # group
            df_result, target_col, best_fitness = match(df, team_template, weights, constraints)
            print("Best fitness:", best_fitness)

            # csv generation
            csv_content = df_result.to_csv(index=False)
            CSVGeneration.objects.create_generation(
                    csv_data=csv_content,
                    team_size=int((constraints['min_size'] + constraints['max_size']) / 2),
                    template_used=team_template,
                    student_count=df.shape[0]
            )

            # create teams for display
            group_col = target_col if target_col else 'teams'
            grouped = df_result.groupby(group_col)
            for name, group in grouped:
                teams.append({
                    'name': name,
                    'members': group.to_dict('records')
                })
            teams.sort(key=lambda x: int(x['name'].split()[-1]) if x['name'].split()[-1].isdigit() else 999)
        else:
            print(form.errors)
    else:
        form = UploadFileForm()
        if 'results' in request.session:
            del request.session['results']

    historical_generations = CSVGeneration.objects.order_by('-id')[:5]

    return render(request, 'allocator/index.html', {
        'form': form,
        'teams': teams,
        'historical_generations': historical_generations
    })


def download_csv(request):
    results = request.session.get('results', [])
    if not results:
        latest_generation = CSVGeneration.objects.first()
        if latest_generation:
            response = HttpResponse(
                content_type='text/csv',
                headers={'Content-Disposition': 'attachment; filename="teams_latest.csv"'},
            )
            response.write(latest_generation.csv_data)
            return response
        return HttpResponse("No results found to download.", content_type='text/plain')

    response = HttpResponse(
        content_type='text/csv',
        headers={'Content-Disposition': 'attachment; filename="teams.csv"'},
    )

    if results:
        fieldnames = list(results[0].keys())
        writer = csv.DictWriter(response, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    return response


def download_historical_csv(request, generation_id):
    generation = get_object_or_404(CSVGeneration, id=generation_id)
    response = HttpResponse(
        content_type='text/csv',
        headers={
            'Content-Disposition':
                f'attachment; filename="teams_{generation.generated_at.strftime("%Y%m%d_%H%M%S")}.csv"'
        },
    )
    response.write(generation.csv_data)
    return response