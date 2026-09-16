# cow-tracking-tool
COMSM3201_2025_AYEAR
A human-in-the-loop cow tracklet refinement and anomaly detection system for multi-camera farm surveillance datasets.

| Stage | Module / Step | Key Features & Purpose | Status |
| :--- | :--- | :--- | :--- |
| **01. Ingestion** | **Data Preparation** | • Organize multi-camera raw image sequences (`image_all/`) and sparse LabelMe JSON annotations (`json/`) | Required |
| **02. Scan** | **`anomaly_detector.py`**<br>*(Batch Anomaly Scanner)* | • Scans all camera sessions for heuristic tracking anomalies (`ID_SWAP`, `UNREALISTIC_JUMP`, `GEOMETRIC_DEFORMATION`)<br>• Generates `<json_root>/anomalies.json` | Required |
| **03. Refine** | **`app_frame.py`**<br>*(Interactive Frame Station)* | • Load images and JSONs to visualize anomalies with red tick markers on `AnomalySlider`<br>• Inspect identity consistency via **Coat Pattern Viewer** ($\pm 3$ frames)<br>• Fine-tune bounding box coordinates, angles, and cow IDs<br>• Changes are automatically saved back to corresponding JSON files | Required |
| **04. Review** | **`app_video.py`**<br>*(Visualization Station)* | • Load cleaned JSON annotations and multi-camera sessions<br>• Runs trajectory interpolation engine for continuous **25 FPS** paths<br>• Smooth video playback for final verification | Optional |