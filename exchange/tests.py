from django.db import IntegrityError
from django.test import TestCase

from accounts.models import StudentProfile, User
from .models import (BuddyAssignment, ExchangeParticipation, ExchangeRoute,
                     Stage, University)
from .services import assign_buddy


def user(email, role, approved=True):
    return User.objects.create_user(
        email=email, password="Passw0rd!", role=role, is_approved=approved)


class ConstraintTests(TestCase):

    def setUp(self):
        self.u1 = University.objects.create(name="Вуз А")
        self.u2 = University.objects.create(name="Вуз Б")
        self.route = ExchangeRoute.objects.create(
            name="А—Б", from_university=self.u1, to_university=self.u2)
        self.curator = user("c@ex.com", User.Role.CURATOR)
        self.student = user("s@ex.com", User.Role.STUDENT)

    def test_route_universities_must_differ(self):
        with self.assertRaises(IntegrityError):
            ExchangeRoute.objects.create(
                name="А—А", from_university=self.u1, to_university=self.u1)

    def test_one_active_participation_per_student(self):
        ExchangeParticipation.objects.create(
            student=self.student, curator=self.curator, route=self.route)
        with self.assertRaises(IntegrityError):
            ExchangeParticipation.objects.create(
                student=self.student, curator=self.curator, route=self.route)

    def test_one_active_buddy_assignment(self):
        p = ExchangeParticipation.objects.create(
            student=self.student, curator=self.curator, route=self.route)
        b1 = user("b1@ex.com", User.Role.BUDDY)
        b2 = user("b2@ex.com", User.Role.BUDDY)
        assign_buddy(self.curator, p, b1)
        assign_buddy(self.curator, p, b2)  # замена: старое закрыто, новое активно
        self.assertEqual(
            BuddyAssignment.objects.filter(participation=p, ended_at__isnull=True).count(), 1)
        self.assertEqual(
            p.buddy_assignments.get(ended_at__isnull=True).buddy, b2)


class AccessTests(TestCase):

    def setUp(self):
        self.u1 = University.objects.create(name="Вуз А")
        self.u2 = University.objects.create(name="Вуз Б")
        self.route = ExchangeRoute.objects.create(
            name="А—Б", from_university=self.u1, to_university=self.u2)
        self.curator = user("c@ex.com", User.Role.CURATOR)
        self.other_curator = user("c2@ex.com", User.Role.CURATOR)
        self.student = user("s@ex.com", User.Role.STUDENT)

    def test_student_cannot_create_university(self):
        self.client.force_login(self.student)
        response = self.client.post("/exchange/universities/create/", {"name": "Хак"})
        self.assertEqual(response.status_code, 302)  # curator_required переводит на home
        self.assertFalse(University.objects.filter(name="Хак").exists())

    def test_curator_cannot_edit_foreign_participation(self):
        p = ExchangeParticipation.objects.create(
            student=self.student, curator=self.curator, route=self.route)
        self.client.force_login(self.other_curator)
        response = self.client.post(f"/exchange/participations/{p.id}/edit/",
                                    {"route": self.route.id, "current_stage": 2})
        self.assertEqual(response.status_code, 403)
        p.refresh_from_db()
        self.assertEqual(p.current_stage, Stage.PREPARATION)

    def test_buddy_field_injection_ignored(self):
        """Подмена закрытого поля: POST с buddy не создаёт назначение."""
        buddy = user("b@ex.com", User.Role.BUDDY)
        self.client.force_login(self.curator)

        StudentProfile.objects.create(user=self.student, curator=self.curator)
        self.client.post(
            f"/exchange/students/{self.student.id}/participation/create/",
            {"route": self.route.id, "current_stage": 1, "buddy": buddy.id})
        p = ExchangeParticipation.objects.get(student=self.student)
        self.assertEqual(p.buddy_assignments.count(), 0)