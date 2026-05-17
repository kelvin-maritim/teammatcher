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
