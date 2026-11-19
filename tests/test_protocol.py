"""Protocol tests. Frames marked "seen" were sent to, or received from, a real fan.

Run with: python -m unittest discover -s tests
"""

import importlib.util
import pathlib
import sys
import unittest

# Load protocol.py on its own, so the tests don't need Home Assistant installed.
_path = pathlib.Path(__file__).parents[1] / "custom_components" / "fan_smart_sync" / "protocol.py"
_spec = importlib.util.spec_from_file_location("fan_smart_sync_protocol", _path)
protocol = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = protocol  # dataclasses look their module up here
_spec.loader.exec_module(protocol)


class Frames(unittest.TestCase):
    def test_status_request(self):  # seen
        self.assertEqual(protocol.status_request().hex().upper(), "40A000000000000000000000E0")

    def test_fan(self):  # seen
        self.assertEqual(protocol.fan_command(0).hex().upper(), "40A100000000FFFFFFFFFF00DC")
        self.assertEqual(protocol.fan_command(1).hex().upper(), "40A100000001FFFFFFFFFF00DD")
        self.assertEqual(protocol.fan_command(2).hex().upper(), "40A100000002FFFFFFFFFF00DE")
        self.assertEqual(protocol.fan_command(3).hex().upper(), "40A100000003FFFFFFFFFF00DF")

    def test_fan_speed_written_like_the_app(self):
        self.assertEqual(protocol.fan_command(10)[5], 0x10)
        with self.assertRaises(ValueError):
            protocol.fan_command(31)

    def test_light(self):  # seen
        self.assertEqual(protocol.light_command(True, 100).hex().upper(), "40A1000000FF64E4FFFFFF0025")
        self.assertEqual(protocol.light_command(True, 30).hex().upper(), "40A1000000FF649EFFFFFF00DF")
        self.assertEqual(protocol.light_command(False, 100).hex().upper(), "40A1000000FF6464FFFFFF00A5")

    def test_light_clamps(self):
        self.assertEqual(protocol.light_command(True, 150), protocol.light_command(True, 100))


class Replies(unittest.TestCase):
    STATUS = bytes.fromhex("40B01023A3000033000000221B")  # seen

    def test_parse_status(self):
        kind, body = protocol.parse(self.STATUS)
        self.assertEqual(kind, protocol.KIND_STATUS)
        s = protocol.parse_status(body)
        self.assertEqual(s.version, "1.0")
        self.assertFalse(s.dc_motor)
        self.assertTrue(s.reversible)
        self.assertEqual(s.speed_count, 3)
        self.assertTrue(s.lower_light)
        self.assertTrue(s.lower_dimmable)
        self.assertFalse(s.upper_light)
        self.assertEqual(s.speed, 0)
        self.assertFalse(s.lower_on)
        self.assertEqual(s.lower_percent, 51)

    def test_running_with_light_on(self):
        body = bytearray(self.STATUS[1:-1])
        body[4] = 0x02
        body[6] = 0x80 | 30
        s = protocol.parse_status(bytes(body))
        self.assertEqual(s.speed, 2)
        self.assertTrue(s.lower_on)
        self.assertEqual(s.lower_percent, 30)

    def test_rejects_bad_frames(self):
        with self.assertRaises(protocol.FrameError):
            protocol.parse(self.STATUS[:-1] + b"\x00")
        with self.assertRaises(protocol.FrameError):
            protocol.parse(self.STATUS[:12])
        with self.assertRaises(protocol.FrameError):
            protocol.parse(b"\x41" + self.STATUS[1:])


if __name__ == "__main__":
    unittest.main()
