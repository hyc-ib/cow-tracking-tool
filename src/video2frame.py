"""
Cattle Tracklet Merge Assistant - Video Frame Extraction Tool

Description:
    Extracts 1 fps frames from MP4 videos and aligns naming with JSON trackers

Credits:
    Original script by Lab Senior
    Modified and optimized for 10x performance upgrade
"""

import subprocess
from pathlib import Path

SOURCE_FPS = 16


def extract_frames_as_jpg(video_root, output_root):
    Path(output_root).mkdir(parents=True, exist_ok=True)
    video_files = list(Path(video_root).rglob("*.mp4"))

    if not video_files:
        print(f"No .mp4 files found in {video_root}")
        return

    for i, video_path in enumerate(video_files):
        video_name = video_path.stem
        print(f"[{i + 1}/{len(video_files)}] Processing: {video_name}")

        current_save_dir = Path(output_root) / video_name
        current_save_dir.mkdir(parents=True, exist_ok=True)

        temp_pattern = str(current_save_dir / "temp_%06d.jpg")
        cmd = [
            "ffmpeg",
            "-i",
            str(video_path),
            "-vf",
            "fps=1",
            "-q:v",
            "2",  # quality about 95%
            "-y",  # overwrite if exists
            temp_pattern,
        ]

        try:
            subprocess.run(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
            )
        except subprocess.CalledProcessError:
            print(f"  ffmpeg failed on: {video_path}")
            continue

        # Rename temp_000001.jpg → {video_name}_frame_{N:06d}.jpg
        temp_files = sorted(current_save_dir.glob("temp_*.jpg"))
        for idx, temp_file in enumerate(temp_files):
            actual_frame_no = idx * SOURCE_FPS
            new_name = (
                current_save_dir / f"{video_name}_frame_{actual_frame_no:06d}.jpg"
            )
            temp_file.rename(new_name)

        print(f"  Done. {len(temp_files)} frames saved to: {current_save_dir}")


if __name__ == "__main__":
    import static_ffmpeg

    static_ffmpeg.add_paths()

    current_dir = Path(__file__).parent.resolve()
    extract_frames_as_jpg(str(current_dir), str(current_dir / "frames"))
