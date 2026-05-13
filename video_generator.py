import io
import logging
import os
import subprocess
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)


def image_to_video(
    image_bytes: bytes,
    duration: int = 10,
    zoom: bool = True,
) -> Optional[bytes]:
    ffmpeg_path = _find_ffmpeg()
    if not ffmpeg_path:
        logger.error("FFmpeg not found. Install it for video generation.")
        return None

    tmp_dir = tempfile.mkdtemp()
    input_path = os.path.join(tmp_dir, "input.png")
    output_path = os.path.join(tmp_dir, "output.mp4")

    try:
        with open(input_path, "wb") as f:
            f.write(image_bytes)

        if zoom:
            filter_complex = (
                "zoompan=z='if(lte(on,1),1.2,1.2+0.1*sin(on*0.5))':"
                f"d={duration*30}:s=1920x1080:fps=30,"
                "fade=t=in:st=0:d=0.5,fade=t=out:st={}:d=1".format(duration - 1)
            )
        else:
            filter_complex = (
                f"fps=30,scale=1920:1080:force_original_aspect_ratio=1,"
                f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
                f"fade=t=in:st=0:d=0.5,fade=t=out:st={duration-1}:d=1"
            )

        cmd = [
            ffmpeg_path,
            "-y",
            "-loop", "1",
            "-i", input_path,
            "-vf", filter_complex,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-t", str(duration),
            "-movflags", "+faststart",
            output_path,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            return None

        with open(output_path, "rb") as f:
            video_bytes = f.read()

        return video_bytes

    except subprocess.TimeoutExpired:
        logger.error("FFmpeg timed out")
        return None
    except Exception as e:
        logger.error(f"Video generation error: {e}")
        return None
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _find_ffmpeg() -> Optional[str]:
    for path in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "ffmpeg"]:
        try:
            result = subprocess.run(
                [path, "-version"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None
