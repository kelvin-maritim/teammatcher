from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from student_side.models import StudentProfile
from .models import TeamSet, Team, TeamAssignment


class TeamSetModelTest(TestCase):

    def test_create_team_set(self):
        ts = TeamSet.objects.create(name="discussion-teams")
        self.assertEqual(str(ts), "discussion-teams")
        self.assertEqual(TeamSet.objects.count(), 1)

    def test_team_set_name_unique(self):
        TeamSet.objects.create(name="case-studies")
        with self.assertRaises(Exception):
            TeamSet.objects.create(name="case-studies")


class TeamModelTest(TestCase):

    def setUp(self):
        self.team_set = TeamSet.objects.create(name="discussion-teams")

    def test_create_team(self):
        team = Team.objects.create(name="Team Alpha", team_set=self.team_set)
        self.assertEqual(str(team), "discussion-teams - Team Alpha")

    def test_team_not_full_by_default(self):
        team = Team.objects.create(name="Team Beta", team_set=self.team_set, max_members=3)
        self.assertFalse(team.is_full)

    def test_team_is_full_when_max_reached(self):
        team = Team.objects.create(name="Team Gamma", team_set=self.team_set, max_members=2)
        for i in range(2):
            sp = StudentProfile.objects.create(student_id=f"STU00{i}")
            TeamAssignment.objects.create(learner=sp, team=team)
        self.assertTrue(team.is_full)


class TeamAssignmentModelTest(TestCase):

    def setUp(self):
        self.team_set = TeamSet.objects.create(name="test-set")
        self.team = Team.objects.create(name="Team A", team_set=self.team_set)
        self.student = StudentProfile.objects.create(student_id="STU001")

    def test_create_assignment(self):
        assignment = TeamAssignment.objects.create(learner=self.student, team=self.team)
        self.assertTrue(assignment.is_active)
        self.assertEqual(str(assignment), "STU001 -> Team A")

    def test_duplicate_assignment_fails(self):
        TeamAssignment.objects.create(learner=self.student, team=self.team)
        with self.assertRaises(Exception):
            TeamAssignment.objects.create(learner=self.student, team=self.team)


class TeamAPITest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.student = StudentProfile.objects.create(student_id="STU999")

    def test_create_and_list_team_set(self):
        response = self.client.post("/api/team-sets/", {"name": "project-teams"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response = self.client.get("/api/team-sets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_team(self):
        ts = TeamSet.objects.create(name="test-set")
        response = self.client.post("/api/teams/", {"name": "Team Alpha", "team_set": ts.id, "max_members": 4})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_cannot_assign_to_full_team(self):
        ts = TeamSet.objects.create(name="full-set")
        team = Team.objects.create(name="Tiny", team_set=ts, max_members=1)
        sp1 = StudentProfile.objects.create(student_id="S001")
        sp2 = StudentProfile.objects.create(student_id="S002")
        self.client.post("/api/assignments/", {"learner": sp1.id, "team": team.id})
        response = self.client.post("/api/assignments/", {"learner": sp2.id, "team": team.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_assignment(self):
        ts = TeamSet.objects.create(name="patch-set")
        team1 = Team.objects.create(name="Team 1", team_set=ts)
        team2 = Team.objects.create(name="Team 2", team_set=ts)
        assignment = TeamAssignment.objects.create(learner=self.student, team=team1)
        response = self.client.patch(f"/api/assignments/{assignment.id}/", {"team": team2.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
