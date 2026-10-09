import tempfile
import unittest
from unittest.mock import patch, MagicMock
from loggers.camera_logger import RTSPVideoRecorder

class FFmpegCameraTests(unittest.TestCase):
    def test_copy_no_fixed_fps(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = RTSPVideoRecorder('rtsp://example.invalid/live', tmp)
            cmd = r._command('ffmpeg')
            self.assertEqual(cmd[cmd.index('-c:v') + 1], 'copy')
            self.assertEqual(cmd[cmd.index('-rtsp_transport') + 1], 'tcp')
            self.assertNotIn('-r', cmd)
            self.assertEqual(cmd[cmd.index('-use_wallclock_as_timestamps') + 1], '1')
            self.assertEqual(cmd[cmd.index('-fflags') + 1], '+genpts')
            self.assertTrue(cmd[-1].endswith('camera.mkv'))

    def test_ffmpeg_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = RTSPVideoRecorder('rtsp://example.invalid/live', tmp)
            with patch('loggers.camera_logger.shutil.which', return_value=None):
                with self.assertRaisesRegex(RuntimeError, 'FFmpeg'):
                    r.start()

    def test_header_only_does_not_count_as_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = RTSPVideoRecorder('rtsp://example.invalid/live', tmp)
            r.output_path.write_bytes(b'x' * 4096)
            self.assertEqual(r._progress_frames(), 0)
            r.progress_path.write_text('frame=N/A\n', encoding='utf-8')
            self.assertEqual(r._progress_frames(), 0)
            r.progress_path.write_text('frame=2\n', encoding='utf-8')
            self.assertEqual(r._progress_frames(), 2)

    def test_start_and_graceful_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = RTSPVideoRecorder('rtsp://example.invalid/live', tmp)
            proc = MagicMock()
            proc.wait.return_value = 0
            def poll():
                # Simulate the first video packet arriving during startup.
                # Later poll() calls (including stop()) must not overwrite
                # FFmpeg's final progress report.
                if not r.progress_path.exists():
                    r.output_path.write_bytes(b'x' * 2048)
                    r.progress_path.write_text(
                        'frame=1\nprogress=continue\n', encoding='utf-8'
                    )
                return None
            proc.poll.side_effect = poll
            with patch('loggers.camera_logger.shutil.which', return_value='ffmpeg'), patch('loggers.camera_logger.subprocess.Popen', return_value=proc), patch('loggers.camera_logger.repair_recording', return_value={'validation': 'ffmpeg_decoded', 'empty_h264_nals_removed': 0}):
                r.start()
                r.progress_path.write_text('frame=77\nprogress=end\n', encoding='utf-8')
                stats = r.stop()
            self.assertEqual(stats['frame_count'], 77)
            self.assertIsNone(stats['error'])
            self.assertTrue(r.metadata_path.exists())
            proc.stdin.write.assert_called_with(b'q\n')

if __name__ == '__main__':
    unittest.main()
