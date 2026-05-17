from django.db import models
from student_side.models import StudentProfile


class TeamSet(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Team(models.Model):
    team_set = models.ForeignKey(TeamSet, on_delete=models.CASCADE, related_name="teams")
    name = models.CharField(max_length=255)
    max_members = models.PositiveIntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("team_set", "name")
        ordering = ["name"]

    def __str__(self):
        return f"{self.team_set.name} - {self.name}"

    @property
    def current_member_count(self):
        return self.assignments.count()

    @property
    def is_full(self):
        return self.current_member_count >= self.max_members


class TeamAssignment(models.Model):
    learner = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="team_assignments")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="assignments")
    assigned_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("learner", "team")
        ordering = ["-assigned_at"]

    def __str__(self):
        return f"{self.learner.student_id} -> {self.team.name}"
