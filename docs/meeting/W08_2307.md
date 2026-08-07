# 23 July, 2026

## Dataset Frame Rate Discrepancy (16 FPS "Ghost Cow" Bug)

* **Issue Description:** 
  * Applying the interpolation algorithm produced visual artifacts / "ghost cows" on the video frames.
* **Root Cause Identified:** 
  * The dataset JSON files follow a naming convention incremented by 25 (e.g., `_frame_000025`), leading to the assumption that it was a 25 FPS dataset.
  * Cross-checking against raw CCTV timestamped footage revealed that the frames actually run at **~16.2 FPS** ($925 \text{ frames} / 57 \text{ seconds} \approx 16.2 \text{ FPS}$).
* **Dataset Availability:**
  * Confirmed with Phoenix that no 25 FPS version of the JSON dataset exists; this is the only data available.
  * The tool/pipeline must adapt to process this 16 FPS timestamped structure.

---

## Interpolation Algorithm Optimization (Geometric Bounding Box)

* **Current Implementation Problem:**
  * Currently interpolating the 4 corner points of the bounding box ($X_1, Y_1 \dots X_4, Y_4$).
  * **Risk:** Accumulating rounding errors over time can cause the box to deform into a non-rectangular shape.
* **Supervisor's Recommendation (5-Parameter Interpolation):**
  * Switch to interpolating **5 core geometric parameters** instead:
    1. Center Coordinates ($X, Y$)
    2. Box Length
    3. Box Width
    4. Rotation Angle ($\theta$)
  * **Benefit:** Guarantees that the interpolated bounding box **always remains a valid rectangle** without geometric distortion.

---

## UI/UX Workflow: Auto-Save & Undo Functionality

* **Current Pain Point:**
  * A pop-up dialog prompts the user to save every single time they switch frames, causing significant interaction friction ("a real pain").
* **Improvement Protocol:**
  * **Remove Per-Frame Save Dialog:** Implement **Auto-Save** background writing (similar to Microsoft Word).
  * **Undo Mechanism:** Add an **Undo function** (storing original state per frame) so users can easily revert accidental modifications.