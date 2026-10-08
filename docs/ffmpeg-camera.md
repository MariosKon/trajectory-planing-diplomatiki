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
