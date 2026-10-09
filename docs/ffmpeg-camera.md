# Experimental FFmpeg RTSP video recorder

Install FFmpeg separately and verify `ffmpeg -version` in PowerShell.
Run offline tests: `python -m unittest discover -s tests -v`.

The logger preserves the existing LoggingManager start/stop calls.
It writes `camera.mkv` using video stream copy (no OpenCV encode and
no 30-FPS duplicate frame insertion), `camera_metadata.json`,
`ffmpeg_camera.log`, and `ffmpeg_camera_progress.txt` per trial.

FFmpeg uses RTSP TCP by default. Stopping sends q to the child process
for graceful file finalization, with a timeout and forced-stop fallback.
Camera errors remain partial recording losses after successful motion.

Host recording timestamps do not imply synchronized camera frame PTS.
Hardware video capture has NOT been tested; verify stream compatibility
and video quality on a single supervised trial before any robot batch.

## Physical camera validation (2026-10-09)

The 45 recorded ServoP trials contained periodically inserted zero-length H.264
NAL units, often near keyframes. A Matroska file can contain real robot motion
and report hundreds of copied frames while failing normal FFmpeg decoding.

After each FFmpeg recording is finalized, the camera logger now validates the
output by decoding it with FFmpeg. For this **single H.264, non-laced video
stream** format, it removes only zero-length NAL entries when present, remuxes
the cleaned packets without re-encoding, rebuilds the Matroska seek index, and
makes duplicate PTS/DTS strictly increasing. If repair succeeds, camera.mkv is
the decoded/validated file and camera_original.mkv retains the exact original
bytes. camera_metadata.json stores video_validation, including the number of
removed empty NAL entries. No original is overwritten on failed repair; the
camera metadata instead records a validation error.

The repair requires FFmpeg with the setts bitstream filter and is limited to
recordings up to 256 MiB. Larger files and unsupported Matroska/H.264 layouts
must be reviewed manually. File-size and FFmpeg frame progress alone are not
proof of decodable footage. Extra validation/repair is performed after the
recording has ended, not while robot motion is in progress.

**Timestamp limitation:** The original stream uses FFmpeg host-arrival/RTSP
timestamps, not synchronized camera exposure times. Cleaning the packets
preserves their approximate timing but does not establish synchronization to
the robot feedback or Rigol. Source logs may still show timestamp warnings;
use video for qualitative documentation, not precise timing measurements.
