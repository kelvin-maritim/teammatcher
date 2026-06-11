from rest_framework import generics, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import TeamSet, Team, TeamAssignment
from .serializers import TeamSetSerializer, TeamSerializer, TeamAssignmentSerializer


class TeamSetListCreateView(generics.ListCreateAPIView):
    queryset = TeamSet.objects.all()
    serializer_class = TeamSetSerializer


class TeamSetDetailView(generics.RetrieveDestroyAPIView):
    queryset = TeamSet.objects.all()
    serializer_class = TeamSetSerializer


class TeamListCreateView(generics.ListCreateAPIView):
    serializer_class = TeamSerializer

    def get_queryset(self):
        queryset = Team.objects.all()
        team_set_id = self.request.query_params.get("team_set")
        if team_set_id:
            queryset = queryset.filter(team_set_id=team_set_id)
        return queryset


class TeamDetailView(generics.RetrieveDestroyAPIView):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer


class TeamAssignmentListCreateView(generics.ListCreateAPIView):
    serializer_class = TeamAssignmentSerializer

    def get_queryset(self):
        queryset = TeamAssignment.objects.all()
        learner_id = self.request.query_params.get("learner")
        team_id = self.request.query_params.get("team")
        if learner_id:
            queryset = queryset.filter(learner_id=learner_id)
        if team_id:
            queryset = queryset.filter(team_id=team_id)
        return queryset

    def create(self, request, *args, **kwargs):
        team_id = request.data.get("team")
        learner_id = request.data.get("learner")
        if not team_id or not learner_id:
            return Response({"error": "Both team and learner are required."}, status=status.HTTP_400_BAD_REQUEST)
        team = get_object_or_404(Team, pk=team_id)
        if team.is_full:
            return Response({"error": f"Team {team.name} is full ({team.max_members} max)."}, status=status.HTTP_400_BAD_REQUEST)
        if TeamAssignment.objects.filter(learner_id=learner_id, team=team).exists():
            return Response({"error": "This learner is already assigned to this team."}, status=status.HTTP_400_BAD_REQUEST)
        return super().create(request, *args, **kwargs)


class TeamAssignmentUpdateView(generics.UpdateAPIView):
    queryset = TeamAssignment.objects.all()
    serializer_class = TeamAssignmentSerializer
    http_method_names = ["patch"]

    def patch(self, request, *args, **kwargs):
        assignment = self.get_object()
        new_team_id = request.data.get("team")
        if new_team_id and int(new_team_id) != assignment.team.id:
            new_team = get_object_or_404(Team, pk=new_team_id)
            if new_team.is_full:
                return Response({"error": f"Target team {new_team.name} is full."}, status=status.HTTP_400_BAD_REQUEST)
            assignment.team = new_team
            assignment.save()
            serializer = self.get_serializer(assignment)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return super().partial_update(request, *args, **kwargs)
# Append to team_management/views.py

from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from services.csv_service import validate_csv_file  # Ensure services/ is in your PYTHONPATH


class CSVUploadValidationView(APIView):
    """
    API view to handle Open edX membership CSV validation.
    Accepts a multipart form-data payload containing a 'file' parameter.
    """
    parser_classes = [MultiPartParser]

    def post(self, request, *args, **kwargs):
        file_obj = request.data.get("file")
        
        if not file_obj:
            return Response(
                {"valid": False, "errors": ["No file was provided under the 'file' parameter."], "warnings": [], "rows": [], "team_sets": []},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # 1. Extract raw byte chunks from the upload wrapper
            file_data = file_obj.read()
            
            # 2. Process using your CSV service logic
            validation_result = validate_csv_file(file_data)
            
            # 3. Determine HTTP Response Status code based on operational validity
            if not validation_result["valid"]:
                return Response(validation_result, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
                
            return Response(validation_result, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"valid": False, "errors": [f"An unexpected system exception occurred: {str(e)}"], "warnings": [], "rows": [], "team_sets": []},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )