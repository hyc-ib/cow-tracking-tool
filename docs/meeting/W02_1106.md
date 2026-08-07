# 11 June, 2026

## 1. Dataset Structure Breakdown (Tong's Data)
* **Storage Hierarchy:** The data is organized by individual cameras, where each camera has its own dedicated folder (e.g., `camera1`).
* **Frames Folder:** Contains a sequence of individual `.jpg` image files extracted from the camera feed.
* **Annotation Package:** Bounding box labels are packaged inside a single zip file named `*_xml.zip` located in the same camera root directory.
* **Frame Rate Specification:** The tracking data and XML annotations are stored at a rate of 1 frame per second (1 fps).
* **Label Content:** The XML files record the explicit mapping between frame filenames and the respective cow bounding boxes (including X, Y coordinates, width, and height).

## 2. Key UI/UX Demo & Progression
* **Backend Data Flow:** The student successfully developed a script to automatically unzip the `*_xml.zip` file into a temporary directory and programmatically pair each `.jpg` frame with its corresponding `.xml` label file.
* **Interactive Slider Blueprint:** Demonstrated the core UI concept using a slider/scrollbar interface. Dragging the slider dynamically updates and displays the absolute path of the active image frame and its associated XML annotation on screen.
* **Prof. Neill's Feedback:** Highly praised the progress, describing the synchronization between the slider and the backend paths as "brilliant" and a great foundational step.

## 3. Next Steps & Technical Objectives (Action Items)
* **[Software] Image & Bounding Box Rendering:** Transition from displaying raw text paths to rendering the actual `.jpg` images directly in the GUI. Overlay the bounding boxes onto the images by parsing the coordinates from the paired XML files.
* **[Data] Video Source Inquiry:** Contact Phoenix via Teams to check if the original high-frame-rate videos (e.g., 25 or 30 fps) for Tong's dataset are available in the lab. This is crucial for Prof. Neill's future research on smoothing algorithms between the 1-fps annotations.
* **[Logistics] Meeting Coordination:** Due to Prof. Neill's upcoming two-week travel schedule, the student will collaborate closely with Phoenix for daily technical support and resume formal check-ins upon the professor's return.