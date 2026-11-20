import unittest

from services import activity_svc


class ActivityServiceTest(unittest.TestCase):
    def setUp(self):
        activity_svc.reset()

    def tearDown(self):
        activity_svc.reset()

    def test_track_marks_running_until_exit(self):
        with activity_svc.track("Price sync"):
            self.assertFalse(activity_svc.is_idle())
            self.assertEqual([item["name"] for item in activity_svc.running()], ["Price sync"])
            self.assertIn("started_at", activity_svc.running()[0])
        self.assertTrue(activity_svc.is_idle())

    def test_nested_track_keeps_outer_running(self):
        with activity_svc.track("FX rate sync"):
            with activity_svc.track("FX rate sync"):
                self.assertEqual(activity_svc.running()[0]["name"], "FX rate sync")
            self.assertFalse(activity_svc.is_idle())
        self.assertTrue(activity_svc.is_idle())

    def test_track_releases_on_exception(self):
        with self.assertRaises(RuntimeError), activity_svc.track("Macro sync"):
            raise RuntimeError("boom")
        self.assertTrue(activity_svc.is_idle())

    def test_decorator_tracks(self):
        seen: list[str] = []

        @activity_svc.tracked("Backup")
        def job():
            seen.extend(item["name"] for item in activity_svc.running())
            return 42

        self.assertEqual(job(), 42)
        self.assertEqual(seen, ["Backup"])
        self.assertTrue(activity_svc.is_idle())

    def test_maintenance_window(self):
        self.assertFalse(activity_svc.in_maintenance())
        with activity_svc.maintenance():
            self.assertTrue(activity_svc.in_maintenance())
        self.assertFalse(activity_svc.in_maintenance())


if __name__ == "__main__":
    unittest.main()
