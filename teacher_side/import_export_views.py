import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db import transaction

from services.csv_service import validate_csv_file

from teacher_side.models import (
    TeamSet,
    Team,
    TeamAssignment
)

from student_side.models import StudentProfile



@csrf_exempt
@login_required
@transaction.atomic
def import_csv(request):

    if request.method != "POST":
        return JsonResponse({
            "success": False,
            "message": "POST request required."
        }, status=405)

    course_id = request.POST.get("course_id")

    if not course_id:
        return JsonResponse({
            "success": False,
            "message": "course_id is required."
        }, status=400)

    csv_file = request.FILES.get("file")

    if not csv_file:
        return JsonResponse({
            "success": False,
            "message": "CSV file is required."
        }, status=400)

    if csv_file.size > 4 * 1024 * 1024:
        return JsonResponse({
            "success": False,
            "message": "Maximum file size is 4MB."
        }, status=400)

    validation_result = validate_csv_file(
        csv_file.read()
    )

    if not validation_result["valid"]:
        return JsonResponse({
            "success": False,
            "errors": validation_result["errors"]
        }, status=400)

    return JsonResponse({
        "success": True,
        "message": "CSV validated successfully.",
        "team_sets": validation_result["team_sets"],
        "rows_found": len(validation_result["rows"]),
        "warnings": validation_result["warnings"]
    })
    
def resolve_student(user_identifier):

    student = StudentProfile.objects.filter(
        student_id=user_identifier
    ).first()

    if student:
        return student

    student = StudentProfile.objects.filter(
        email=user_identifier
    ).first()

    if student:
        return student

    return None