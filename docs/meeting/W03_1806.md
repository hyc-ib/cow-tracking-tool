# 18 June, 2026

## 1. Bounding Box Correction & Geometric Debugging
* **Angle Unit Discrepancy:** The bounding box rotation angles provided in Tong's XML files are highly likely specified in **radians** rather than degrees, given the small values observed[cite: 511, 512, 513].  The rendering logic must account for this ($0 \text{ to } 360^\circ \equiv 0 \text{ to } 2\pi$).
* **Coordinate Swap Suspected:** The currently rendered bounding boxes look incorrect (distorted rectangles). It is strongly suspected that X and Y coordinates (or width and height attributes) might be swapped in the layout assignment. 
* **Target Definition Clarification:** Bounding boxes must strictly fit and encapsulate the **cow's torso (body)** only, intentionally excluding the head and the tail.
* **Read/Write Requirement:** The tool must ultimately be capable of not only reading but also rewriting/modifying these updated XML files back to disk.

## 2. Advanced Features: Cross-Camera Sync & Data Interpolation
* **Multi-View Synchronization:** The current iteration only tracks a single view. The next phase requires a feature where clicking on a specific Cow ID automatically loads and synchronizes adjacent cameras tracking the same cow within a 5-minute window, popping up multiple views simultaneously.
* **Frame Rate Interpolation:** Develop a feature to interpolate the sparse 1-fps tracklets into a smoother 25 or 30 Hz (frames per second) sequence.
* **Interpolation Logic:** Linear interpolation should be applied to spatial positions, whereas **spherical/circular interpolation** must be used for rotation angles to prevent flipping anomalies between $0^\circ$ and $360^\circ$.

## 3. UI/UX Design Philosophy: Speed & Hotkeys
* **Strict Efficiency Rule:** The total time spent by a human operator correcting a single bounding box must be minimal. 
* **Zero Dropdowns Policy:** The interface must avoid dropdown menus or tedious option clicking.
* **Keyboard Shortcuts Driven:** The system must heavily rely on fluid keyboard shortcuts for translation (moving) and rotation, requiring as few key presses as possible.

## 4. Dataset Strategy (Tong's Data vs. Phoenix's Data)
* **Tong's Data Inconsistency:** Some folders/cameras in Tong's dataset currently lack XML files or use divergent formatting because they are not yet fully processed by the lab. 
* **Fallback Protocol:** If the missing components of Tong's data do not arrive within the next two weeks, the project will permanently pivot to using **Phoenix's dataset**.  Phoenix's data is more straightforward and contains all necessary components.
* **Seamless Compatibility:** The final tool should ideally handle both datasets seamlessly without requiring explicit manual format toggling from the user.

## 5. Timeline & Logistics During Supervisor's Absence
* **Two-Week Standby:** Prof. Neill will be away for the next two weeks (returning on a Monday). 
* **Primary Technical Support:** Phoenix remains the active day-to-day point of contact for any script blockages or data structure inquiries.
* **Teams Progress Log:** While Prof. Neill will be "read-only" on Teams, students are encouraged to post interesting screenshots and progress updates, which he will review remotely.