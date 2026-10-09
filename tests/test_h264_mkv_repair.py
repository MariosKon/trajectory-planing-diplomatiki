import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from loggers.h264_mkv_repair import (
    _size_bytes, strip_empty_h264_nals, repair_recording,
)


def element(id_bytes, value):
    return id_bytes + _size_bytes(len(value), 1) + value


def example(empty=True):
    # SimpleBlock: track=1, time=0, keyframe, NAL length=2, NAL payload.
    block = b'\x81\x00\x00\x80' + (b'\x00' * 4 if empty else b'') + b'\x00\x00\x00\x02\x65\x88'
    cluster = element(b'\x1f\x43\xb6\x75', element(b'\xa3', block))
    return element(b'\x1a\x45\xdf\xa3', b'') + element(b'\x18\x53\x80\x67', cluster)


class H264MKVRepairTests(unittest.TestCase):
    def test_strips_only_empty_nals(self):
        raw = example()
        cleaned, count = strip_empty_h264_nals(raw)
        self.assertEqual(count, 1)
        self.assertEqual(len(raw) - len(cleaned), 4)
        self.assertEqual(strip_empty_h264_nals(cleaned), (cleaned, 0))
        self.assertTrue(cleaned.endswith(b'\x00\x00\x00\x02\x65\x88'))

    def test_clean_video_unmodified(self):
        data = example(empty=False)
        self.assertEqual(strip_empty_h264_nals(data), (data, 0))

    def test_invalid_length_fails_closed(self):
        bad = example().replace(b'\x00\x00\x00\x02\x65\x88', b'\x00\x00\x00\x40\x65\x88')
        with self.assertRaisesRegex(ValueError, 'length exceeds'):
            strip_empty_h264_nals(bad)

    def test_lacing_fails_closed(self):
        bad = example().replace(b'\x81\x00\x00\x80', b'\x81\x00\x00\x82')
        with self.assertRaisesRegex(ValueError, 'Laced'):
            strip_empty_h264_nals(bad)

    def test_invalid_video_not_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'camera.mkv'
            raw = example()
            p.write_bytes(raw)

            def mocked_run(command, **kwargs):
                if '-bsf:v' in command:
                    Path(command[-1]).write_bytes(b'not a playable video')
                    return CompletedProcess(command, 0, '', '')
                return CompletedProcess(command, 1, '', 'bad decode')

            with patch('loggers.h264_mkv_repair.subprocess.run', side_effect=mocked_run):
                with self.assertRaisesRegex(RuntimeError, 'decode failed'):
                    repair_recording(p)

            self.assertEqual(p.read_bytes(), raw)
            self.assertFalse((p.parent / 'camera_original.mkv').exists())
            self.assertFalse((p.parent / 'camera_repair_input.mkv').exists())
            self.assertFalse((p.parent / 'camera_repair_output.mkv').exists())


if __name__ == '__main__':
    unittest.main()
