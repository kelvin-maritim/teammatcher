from django.db import models
from django.utils import timezone


class TeamNameTemplate(models.Model):
    name = models.CharField(max_length=100, help_text="Template name (e.g., 'Marvel Heroes')")
    team_names = models.TextField(
    blank=True,
    null=True,
    help_text="List of team names as JSON string"
)
    created_at = models.DateTimeField(auto_now_add=True)
    is_default = models.BooleanField(
        default=False,
        help_text="Mark this template as the default selection"
    )

    class Meta:
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.name} ({len(self.team_names)} teams)"

    def save(self, *args, **kwargs):
        if self.is_default:
            TeamNameTemplate.objects.filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)


class CSVGenerationManager(models.Manager):
    def create_generation(self, csv_data, team_size, template_used, student_count):
        generation = self.create(
            csv_data=csv_data,
            team_size=team_size,
            template_used=template_used,
            student_count=student_count
        )
        
        all_generations = self.order_by('-generated_at')
        if all_generations.count() > 5:
            old_generations = all_generations[5:]
            old_ids = [gen.id for gen in old_generations]
            self.filter(id__in=old_ids).delete()
        
        return generation


class CSVGeneration(models.Model):
    csv_data = models.TextField(help_text="CSV content as text")
    team_size = models.IntegerField(help_text="People per team")
    template_used = models.ForeignKey(
        TeamNameTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Team name template used (if any)"
    )
    generated_at = models.DateTimeField(default=timezone.now)
    student_count = models.IntegerField(help_text="Total number of students")

    objects = CSVGenerationManager()

    class Meta:
        ordering = ['-generated_at']
        verbose_name = "CSV Generation"
        verbose_name_plural = "CSV Generations"

    def __str__(self):
        template_name = self.template_used.name if self.template_used else "Default"
        return f"{self.generated_at.strftime('%Y-%m-%d %H:%M')} - {self.student_count} students - {template_name}"


# class Student(models.Model):
#     student_id = models.CharField(primary_key=True, max_length=50)
#     vector = models.TextField()
