# 13 July, 2026

## Current Progress & Completed Features
The core layout and basic data loop of the application are working as expected:
* **Frame Navigation**: Users can slide the time slider to change frames or type a specific frame number to jump directly to it.
* **Bounding Box Interaction**: Users can select and move bounding boxes on the canvas, then save the updated annotations directly back to the file.
* **Rotation Feature**: Currently developing a rotation function (using the `Shift` key) to manually adjust box angles, which is especially helpful when cows turn.

---

## Dataset Limitations & Challenges
* **Phoenix's Dataset**: Discussed the data structure with Phoenix. His dataset includes camera IDs but contains **no absolute localization info** (no exact bounding box coordinates); it only consists of pre-segmented cow images.
* **Core Problem**: AI tracking tracking systems frequently swap IDs or fail when two cows cross each other. The main goal of this tool must be providing a fast and efficient way for users to spot these errors and confirm data consistency.

---

## Proposed Diagnostic Tools (Next Tasks)
To help users quickly find where the AI went wrong without checking every single frame, the following feature ideas were proposed:

### 1. Bounding Box Pixel Sampling
* **Concept**: When a user clicks a cow ID, the tool will sample the pixels inside its bounding boxes across frames and show them side-by-side (left to right) as a single snapshot.
* **Purpose**: Since a cow's coat pattern stays the same, users can easily tell at a glance if the identity remains consistent or if another cow was accidentally mixed in.

### 2. Smart Jump to Error-Prone Areas
* **Concept**: Build an algorithm to automatically flag frames with high error risks. 
* **Target Areas**: 
  * Points where two bounding boxes cross paths (the most common tracking failure point).
  * Sudden acceleration, abrupt jumps, or sudden changes in a box's position.
* **Purpose**: Allows the user to skip the correct parts and jump straight to problematic frames for quick manual verification.

### 3. Trajectory & Rotation Graph Plotting
* **Concept**: Plot curves showing the cow's $X$-position against time, as well as its rotation over time.
* **Purpose**: The original ground-truth data is sparse (labeled roughly 1 in 25 frames). The tool interpolates the missing frames to create a continuous frame-by-frame timeline. Plotting these lines helps users visually spot unnatural spikes, jagged movements, or massive gaps that indicate interpolation errors.