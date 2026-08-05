# cow-tracking-tool
COMSM3201_2025_AYEAR

┌──────────────────────────────────────────────────────────────────────────┐
│ 1. app_frame.py (Annotation & Refinement Station)                        │
├──────────────────────────────────────────────────────────────────────────┤
│  • Navigate frames using A / D hotkeys                                   │
│  • Inspect & correct ID swaps using the Pattern Matching Tool            │
│  • Fine-tune bounding box positions, rotation angles, & box detections   │
│  • Auto-save cleaned JSON annotation files                               │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ 2. app_video.py (Visualization & Review Station)                         │
├──────────────────────────────────────────────────────────────────────────┤
│  • Load cleaned JSON annotation files                                    │
│  • Automatically run interpolation_engine to generate dense 25 FPS paths │
│  • Smooth video playback for final outcome verification                  │
└──────────────────────────────────────────────────────────────────────────┘
