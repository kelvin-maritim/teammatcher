from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class TeamSet(models.Model):
    name = models.CharField(max_length=255)
    course_id = models.CharField(max_length=255, db_index=True)  # NEW: course association
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("name", "course_id")  # same name can exist in different courses
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.course_id})"


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
    learner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="team_assignments")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="assignments")
    assigned_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("learner", "team")
        ordering = ["-assigned_at"]

    def __str__(self):
        return f"{self.learner.username} -> {self.team.name}"


class CourseEnrollment(models.Model):
    MODE_CHOICES = [
        ('audit', 'Audit'),
        ('verified', 'Verified'),
        ('masters', 'Masters'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    course_id = models.CharField(max_length=255, db_index=True)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)

    class Meta:
        unique_together = ('user', 'course_id')

    def __str__(self):
        return f"{self.user.username} – {self.course_id} ({self.mode})"