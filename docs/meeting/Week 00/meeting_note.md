# 26 May, 2026

## 1. Project Philosophy & Guidelines (Prof. Neill)
* **Real-World Impact:** All MSc projects must utilize real farm data and provide genuine utility to the lab's ongoing research rather than being discarded post-graduation.
* **Risk Management:** Students without extensive High-Performance Computing (HPC) or deep learning background are advised to avoid high-risk infrastructure setups (e.g., Slurm queuing, cluster debugging) that consume limited time.
* **Academic Success:** The primary objective is to demonstrate a rigorous scientific process and experimental understanding, which guarantees a good mark, regardless of whether the final AI model outperforms previous benchmarks.
* **Project Spectrum:** Projects range from 100% software engineering (parsing JSON/XML files, developing GUIs) to highly specialized deep learning research.

## 2. PhD Project Overviews & Current Challenges

### A. Huimin — Cattle Behavior Recognition
* **Methodology:** Crops individual cows from raw farm videos into short 10-second clips and feeds them into video classification models to detect specific behavioral labels.
* **Target Behaviors:** Includes standing, walking, lying, and the physical transitions between standing and lying.
* **Core Bottlenecks:** * Certain crucial behaviors (e.g., self-grooming) are incredibly rare in the massive dataset, making data collection slow and difficult.
  * Veterinary annotators often struggle to understand the massive volume of data required to train robust computer vision models.
  * The lab currently lacks structured data regarding cattle-to-cattle social interactions, physical contact, or bullying behaviors.

### B. Phoenix — Cattle Re-Identification (Re-ID) & Tracking
* **Methodology:** Focuses on identifying the same individual cows across multiple non-overlapping cameras by utilizing contrastive learning pipelines (e.g., NT-Xent loss) to cluster cattle features in an embedding/latent space.
* **Data Characteristics:** Employs YOLO-based rotated bounding boxes and Segment Anything 3 (SAM3) polygon masks to isolate cow textures while blurring out background noise like floor straw.
* **Core Bottlenecks:** * Even state-of-the-art trackers consistently fail when cows overlap, cross paths, or crowd closely together, resulting in fragmented tracking segments ("broken tracklets").
  * Resolving these broken tracklets currently relies on extensive, highly inefficient manual observation and manual annotation by human operators.

## 3. MSc Project Allocation & Scope (My Project)
* **Project Title/Focus:** Fixing Broken Tracklets in Cattle Tracking Data.
* **Objective:** Design and implement a Graphical User Interface (GUI) software tool that allows a human operator to rapidly review, validate, merge, or split fragmented tracking data.
* **Technical Strategy:** Combine robust data engineering pipelines with an intuitive user experience to eliminate blind manual directory searching, saving hours of lab annotation time.
* **Target Dataset:** Prioritize Tong's dataset for the initial prototype phase due to its structured nature and consistent 1 frame-per-second markup format.

## 4. Operational Next Steps & Supervision Timeline
* **Communication Channel:** A shared Microsoft Teams group will be created for the cohort to facilitate cross-over technical discussions and data sharing.
* **Supervision Structure:** Weekly one-on-one meetings will be held with Prof. Neill, alongside an assigned PhD mentor for day-to-day technical support (e.g., Python troubleshooting, data access).
* **First-Week Milestones:** Focus on understanding the target data structures, completing initial data parsing scripts, and formulating the core software architecture requirements.