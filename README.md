# cow-tracking-tool
COMSM3201_2025_AYEAR

| Stage | Module | Key Features |
| :--- | :--- | :--- |
| **01. Refine** | **`app_frame.py`**<br>*(Annotation Station)* | • Navigate frames using `A` / `D` hotkeys<br>• Inspect & correct ID swaps using **Pattern Matching Tool**<br>• Fine-tune bounding box positions, angles, & detections<br>• Auto-save cleaned JSON annotation files |
| **↓** | | *Outputs Cleaned JSON Annotations* |
| **02. Review** | **`app_video.py`**<br>*(Visualization Station)* | • Load cleaned JSON annotation files<br>• Automatically run `interpolation_engine` for dense **25 FPS** paths<br>• Smooth video playback for final outcome verification |
