from rest_framework import serializers
from .models import TeamSet, Team, TeamAssignment


class TeamSetSerializer(serializers.ModelSerializer):
    team_count = serializers.SerializerMethodField()

    class Meta:
        model = TeamSet
        fields = ["id", "name", "description", "team_count", "created_at", "updated_at"]

    def get_team_count(self, obj):
        return obj.teams.count()


class TeamSerializer(serializers.ModelSerializer):
    team_set_name = serializers.CharField(source="team_set.name", read_only=True)
    current_member_count = serializers.ReadOnlyField()
    is_full = serializers.ReadOnlyField()

    class Meta:
        model = Team
        fields = ["id", "name", "team_set", "team_set_name", "max_members", "current_member_count", "is_full", "created_at", "updated_at"]


class TeamAssignmentSerializer(serializers.ModelSerializer):
    learner_student_id = serializers.CharField(source="learner.student_id", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)

    class Meta:
        model = TeamAssignment
        fields = ["id", "learner", "learner_student_id", "team", "team_name", "is_active", "assigned_at", "updated_at"]
        validators = []

    def update(self, instance, validated_data):
        instance.team = validated_data.get("team", instance.team)
        instance.is_active = validated_data.get("is_active", instance.is_active)
        instance.save()
        return instance
