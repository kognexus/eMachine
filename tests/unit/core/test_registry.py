"""T32-2: plugin registry of emachine.core."""

import threading
import time
import unittest

from emachine.core import registry


class RegistryTest(unittest.TestCase):
    def setUp(self):
        self.saved = registry.snapshot()

    def tearDown(self):
        registry.restore(self.saved)

    def test_register_create_and_list(self):
        @registry.register("solver", "fake")
        class Fake:
            def __init__(self, scale=1):
                self.scale = scale

        self.assertIs(registry.get("solver", "fake"), Fake)
        self.assertEqual(registry.create("solver", "fake", scale=3).scale, 3)
        self.assertIn("fake", registry.names("solver"))

    def test_unknown_kind_and_name(self):
        with self.assertRaises(registry.RegistryError):
            registry.register("gearbox", "x")
        with self.assertRaises(registry.RegistryError) as raised:
            registry.get("solver", "nope")
        self.assertIn("nope", str(raised.exception))

    def test_duplicate_name(self):
        @registry.register("optimizer", "dup")
        class A:
            pass
        with self.assertRaises(registry.RegistryError):
            @registry.register("optimizer", "dup")
            class B:
                pass

    def test_registering_the_same_class_twice_is_harmless(self):
        class A:
            pass
        registry.register("optimizer", "same")(A)
        registry.register("optimizer", "same")(A)          # e.g. a module imported twice
        self.assertIs(registry.get("optimizer", "same"), A)

    def test_autoload_is_complete_for_every_thread(self):
        """Rotor positions are solved in a thread pool: a lookup must wait until the autoload has finished
        (before the fix, every thread but the first saw an empty registry)."""
        saved_autoload = dict(registry._autoload)

        def slow_autoload():
            time.sleep(0.05)
            registry.register("geometry", "late")(type("Late", (), {}))

        registry.set_autoload(slow_autoload)
        found, errors = [], []

        def look_up():
            try:
                found.append(registry.get("geometry", "late"))
            except registry.RegistryError as error:
                errors.append(error)

        threads = [threading.Thread(target=look_up) for _ in range(8)]
        try:
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        finally:
            registry._autoload.update(saved_autoload)
        self.assertEqual(errors, [])
        self.assertEqual(len(found), 8)

    def test_kinds(self):
        self.assertEqual(set(registry.KINDS), {"machine", "geometry", "solver", "optimizer"})


if __name__ == "__main__":
    unittest.main()
