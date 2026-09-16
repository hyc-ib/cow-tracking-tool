# System Architecture & Design

This document details the software architecture, data pipelines, and component interactions of the Cattle Tracklet Refinement and Anomaly Detection System.

---

## 1. High-Level System Architecture

The system is organized into a five-tier architecture covering data ingestion, heuristic error scanning, trajectory interpolation, human-in-the-loop manual refinement, and downstream validation:

```mermaid
flowchart TD
    %% Styling
    classDef storage fill:#f9f9f9,stroke:#666,stroke-width:1px;
    classDef core fill:#e1f5fe,stroke:#0288d1,stroke-width:1.5px;
    classDef ui fill:#fff3e0,stroke:#f57c00,stroke-width:1.5px;
    classDef output fill:#e8f5e9,stroke:#388e3c,stroke-width:1.5px;

    subgraph Layer1 ["1. Data Ingestion Layer"]
        RawImgs["Raw Frames (image_all/)<br/>Sequential JPGs (~16.2 FPS)"]:::storage
        RawJSON["Sparse Annotations (json/)<br/>LabelMe Format (Polygon BBoxes)"]:::storage
    end

    subgraph Layer2 ["2. Anomaly Detection Engine (anomaly_detector.py)"]
        R1["Rule 1: ID Swap<br/>(Centroid dist < 60 px)"]:::core
        R2["Rule 2: Unrealistic Jump<br/>(Velocity > 300 px/s)"]:::core
        R4["Rule 3: Geometric Deformation<br/>(Δθ > 45° or ΔArea > 50%)"]:::core
        AnomalyJSON["anomalies.json<br/>(Structured Issue Catalog)"]:::storage

        RawJSON --> R1 & R2 & R4
        R1 & R2 & R4 --> AnomalyJSON
    end

    subgraph Layer3 ["3. Interpolation & Smoothing Engine (interpolation_engine.py)"]
        Param["5-Param Decomposition<br/>(cx, cy, w, h, θ)"]:::core
        Lerp["Linear Spatial Interpolation<br/>(Coordinate & Size Gap Filling)"]:::core
        Slerp["Circular Angle Smoothing<br/>(Direction Continuity)"]:::core
        DenseCache["Dense Trajectory Cache<br/>(Interpolated to 25 FPS)"]:::storage

        RawJSON --> Param --> Lerp --> Slerp --> DenseCache
    end

    subgraph Layer4 ["4. Human-in-the-Loop Refinement (app_frame.py)"]
        Slider["AnomalySlider<br/>(Red Ticks & Issue Navigation [F])"]:::ui
        Canvas["Interactive Annotation Canvas<br/>(Translation, Rotation, Add [N], Delete)"]:::ui
        Strip["Coat Pattern Viewer<br/>(±3 Frames Derotated Crops)"]:::ui

        AnomalyJSON --> Slider
        RawImgs --> Canvas
        RawImgs --> Strip
        RawJSON <-->|Read & Auto-Save| Canvas
    end

    subgraph Layer5 ["5. Review & Downstream Layer (app_video.py)"]
        CleanJSON["Cleaned JSON Annotations"]:::output
        VideoPlayer["Synchronized Multi-View Player<br/>(25 FPS Validation)"]:::ui
        Downstream["Downstream Research Models<br/>(Action Classification, Re-ID)"]:::output

        Canvas --> CleanJSON
        CleanJSON --> VideoPlayer
        DenseCache --> VideoPlayer
        CleanJSON --> Downstream
    end
```

---

## 2. Component Specifications

### 2.1 Data Storage Layer (`image_all/` & `json/`)
* **Image Sequences**: Multi-camera sequential frames extracted at source frame rates (default ~16.2 FPS).
* **LabelMe JSON Format**: Stores sparse bounding box coordinates, class labels (`"cow"`), and persistent tracking identities (`group_id`).

### 2.2 Anomaly Detector (`anomaly_detector.py`)
A batch heuristic processing pipeline acting as a high-recall filter:
* **ID_SWAP**: Detects spatial identity collisions where bounding boxes with distinct IDs have centroids closer than a Euclidean distance threshold ($d < 60\text{ px}$) across adjacent frames.
* **UNREALISTIC_JUMP**: Evaluates spatial velocity per cow ID ($v = \frac{\Delta \text{dist}}{\Delta t}$) and flags movements exceeding realistic biological bounds ($v > 300\text{ px/s}$).
* **GEOMETRIC_DEFORMATION**: Monitors rapid rotation variance ($\Delta \theta > 45^\circ$) or sudden area fluctuations ($\Delta A > 50\%$) derived via `cv2.minAreaRect`.

### 2.3 Interactive Annotation UI (`app_frame.py`)
Built on **PyQt6** for fast desktop rendering:
* **`AnomalySlider`**: Custom `QSlider` dynamically rendering red tick marks at anomaly frame locations based on `anomalies.json`.
* **Coat Pattern Viewer**: Renders cropped, de-rotated bounding box patches across $\pm 3$ frames relative to the current position to verify pelage patterns without leaving the focus area.
* **Interactive Canvas**: Translates click-and-drag interactions into bounding box displacements and rotation angles ($\pm 1^\circ$ or $\pm 5^\circ$) with instant serialization to JSON.

### 2.4 Interpolation & Smoothing Engine (`interpolation_engine.py`)
* Converts discrete 4-point bounding boxes into 5 degrees of freedom $(cx, cy, w, h, \theta)$.
* Interpolates sparse ground truth keyframes (e.g., 1 Hz) into continuous 25 FPS tracklets using linear interpolation for spatial parameters and circular angle interpolation for heading angles.

---

## 3. Data Flow & Interaction Sequence

```mermaid
sequenceDiagram
    autonumber
    actor User as Annotator
    participant Disc as File System (JSON/Images)
    participant Detector as anomaly_detector.py
    participant AppFrame as app_frame.py
    participant Engine as interpolation_engine.py
    participant AppVideo as app_video.py

    %% Phase 1: Automated Detection
    Note over User,Detector: Phase 1: Batch Heuristic Scanning
    User->>Detector: Run batch scan on json/ directory
    Detector->>Disc: Read LabelMe JSON frames
    Detector->>Detector: Compute spatial distances, velocity & bbox delta
    Detector->>Disc: Write anomalies.json

    %% Phase 2: Manual Inspection
    Note over User,AppFrame: Phase 2: Human-in-the-Loop Refinement
    User->>AppFrame: Launch interactive GUI
    AppFrame->>Disc: Load image sequence, JSONs & anomalies.json
    AppFrame->>AppFrame: Mark red ticks on AnomalySlider
    User->>AppFrame: Press 'F' (Next Issue)
    AppFrame->>AppFrame: Display frame & render Coat Pattern Viewer (±3f)
    User->>AppFrame: Adjust Box / Modify Cow ID
    AppFrame->>Disc: Auto-save modifications back to JSON

    %% Phase 3: Interpolation & Verification
    Note over User,AppVideo: Phase 3: Trajectory Review
    User->>AppVideo: Launch verification player
    AppVideo->>Disc: Read cleaned JSON annotations
    AppVideo->>Engine: Request continuous trajectory generation
    Engine->>Engine: Interpolate coordinates (cx, cy, w, h) & smooth angles (θ)
    Engine-->>AppVideo: Return dense 25 FPS tracklets
    AppVideo->>User: Play back synchronized multi-camera video
```
