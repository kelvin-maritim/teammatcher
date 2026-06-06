import csv
import io
import json

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST
import pandas as pd

from student_side.models import StudentProfile

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
        # team_size stored as avg(min,max), so +1 approximates actual max
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
@require_GET
def dashboard_api_mismatch(request):
    """
    GET /teacher/dashboard/api/mismatch/?student=s-001&members=s-002,s-003
    Compares the dragged student's profile against target team members.
    Returns { warnings: [string] } — empty list means no issues found.
    """
    student_id = request.GET.get("student", "").strip()
    members_param = request.GET.get("members", "").strip()
    member_ids = [m.strip() for m in members_param.split(",") if m.strip()]

    if not student_id:
        return JsonResponse({"warnings": [], "error": "student param required"}, status=400)

    try:
        profile = StudentProfile.objects.get(student_id=student_id)
    except StudentProfile.DoesNotExist:
        return JsonResponse({"warnings": [], "no_profile": True})

    member_profiles = list(StudentProfile.objects.filter(student_id__in=member_ids))
    if not member_profiles:
        return JsonResponse({"warnings": [], "no_profile": False})

    warnings = []

    # ── Commitment mismatch ──────────────────────────────────
    if profile.commitment:
        team_commitments = [p.commitment for p in member_profiles if p.commitment]
        mismatched = [c for c in team_commitments if c != profile.commitment]
        if mismatched and len(mismatched) == len(team_commitments):
            unique = list(set(mismatched))
            warnings.append(
                f"Commitment mismatch: {student_id} is \"{profile.commitment}\" "
                f"but team members are \"{', '.join(unique)}\""
            )

    # ── Availability overlap (compare actual time slots) ──────────────
    days = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]

    def get_slots(p):
        slots = set()
        for d in days:
            val = getattr(p, f"availability_{d}", "") or ""
            for slot in val.split(","):
                slot = slot.strip()
                if slot:
                    slots.add((d, slot))
        return slots

    student_slots = get_slots(profile)
    if student_slots:
        overlap_scores = []
        for mp in member_profiles:
            member_slots = get_slots(mp)
            if member_slots:
                overlap = len(student_slots & member_slots) / len(student_slots)
                overlap_scores.append(overlap)
        if overlap_scores:
            avg_overlap = sum(overlap_scores) / len(overlap_scores)
            if avg_overlap < 0.3:
                warnings.append(
                    f"Low availability overlap: {student_id} shares fewer than 30% "
                    f"of their time slots with this team ({int(avg_overlap*100)}% overlap). "
                    f"Scheduling meetings may be difficult."
                )

        # ── Experience level gap ─────────────────────────────────
    level_map = {"beginner": 1, "intermediate": 2, "advanced": 3}
    my_level = level_map.get((profile.experience_level or "").lower(), 0)
    if my_level:
        team_levels = [
            level_map.get((p.experience_level or "").lower(), 0)
            for p in member_profiles
        ]
        team_levels = [l for l in team_levels if l]
        if team_levels:
            avg_level = sum(team_levels) / len(team_levels)
            if abs(my_level - avg_level) > 1.5:
                warnings.append(
                    f"Experience level gap: {student_id} is \"{profile.experience_level}\" "
                    f"while the team average is significantly different"
                )

    # ── Preferred tasks overlap ──────────────────────────────
    my_tasks = set(profile.preferred_tasks.values_list("id", flat=True))
    if my_tasks:
        any_overlap = any(
            my_tasks & set(p.preferred_tasks.values_list("id", flat=True))
            for p in member_profiles
        )
        if not any_overlap:
            warnings.append(
                f"No shared task interests: {student_id} has no preferred tasks "
                f"in common with any current team member"
            )

    return JsonResponse({"warnings": warnings, "no_profile": False})


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
            grouped = df_result.groupby(target_col)
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