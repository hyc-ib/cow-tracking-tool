"""
Cattle Tracklet Merge Assistant - Video Frame Extraction Tool

Description:
    Extracts 1 fps frames from MP4 videos and aligns naming with JSON trackers

Credits:
    Original script by Lab Senior
    Modified and optimized for 10x performance upgrade
"""

import os
import cv2
import subprocess
from pathlib import Path


def extract_frames_as_jpg(video_root, output_root):
    os.makedirs(output_root, exist_ok=True)
    video_files = list(Path(video_root).rglob("*.mp4"))

    if not video_files:
        print(f"Not found any .mp4 files in {video_root}")
        return

    for i, video_path in enumerate(video_files):
        video_name = video_path.stem
        print(f"[{i + 1}/{len(video_files)}] Processing video: {video_name}")

        # Open the video file
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            print(f"Failed to open video: {video_path}")
            continue

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 25  # default to 25 if unable to get fps

        # Calculate the frame interval to extract one frame per second
        frame_interval = int(fps)
        current_save_dir = os.path.join(output_root, video_name)
        os.makedirs(current_save_dir, exist_ok=True)

        temp_pattern = os.path.join(current_save_dir, "temp_%06d.jpg")
        cmd = [
            "ffmpeg",
            "-i",
            str(video_path),
            "-vf",
            "fps=1",
            "-q:v",
            "2",  # 2 means QUALITY=95
            "-y",  # overwrite output files if they exist
            temp_pattern,  # e.g., temp_000001.jpg
        ]

        subprocess.run(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
        )

        # naming rule: temp_000001.jpg -> XXX_frame_000025.jpg
        temp_files = sorted(list(Path(current_save_dir).glob("temp_*.jpg")))
        for idx, temp_file in enumerate(temp_files):
            second_idx = idx + 1
            actual_frame_no = second_idx * frame_interval
            new_name = (
                Path(current_save_dir) / f"{video_name}_frame_{actual_frame_no:06d}.jpg"
            )
            temp_file.rename(new_name)

        saved_count = len(temp_files)

        cap.release()
        print(f"Completed. {saved_count} JPG images saved to: {current_save_dir}")


if __name__ == "__main__":
    import static_ffmpeg

    static_ffmpeg.add_paths()

    current_dir = Path(__file__).parent.resolve()
    video_folder = str(current_dir)
    frame_folder = str(current_dir / "frames")

    # QUALITY = 95
    # extract_frames_as_jpg(video_folder, frame_folder, jpg_quality=QUALITY)
    extract_frames_as_jpg(video_folder, frame_folder)
