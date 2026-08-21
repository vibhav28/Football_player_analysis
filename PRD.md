# Product Requirements Document (PRD)

## PitchTrack — Football Video Analytics Web Application

**Version:** 1.0
**Status:** MVP Planning
**Owner:** Vibhav Thakur
**Date:** August 2026

---

## 1. Product Overview

### 1.1 Product Name

PitchTrack

Working title; the name can be changed later.

### 1.2 Product Summary

PitchTrack is a web-based football video analytics application that allows a user to upload a pre-recorded football match or training video and automatically analyze player movement using Computer Vision.

The system processes the uploaded video and provides:

* Player detection
* Player tracking
* Team classification
* Ball tracking
* Player speed
* Minimum speed
* Maximum speed
* Average speed
* Total distance covered
* Annotated video with tracking overlays

The first version is intentionally designed to work without a database.

The application will initially use:

* Local file storage for uploaded videos
* JSON files for analysis metadata and results
* Temporary processing files
* In-memory application state where appropriate

A database will only be introduced if the requirements cannot be reasonably supported using file-based storage.

If a database becomes necessary, Django will be used as the database/backend framework rather than introducing a separate database architecture prematurely.

---

## 2. Problem Statement

Football performance tracking systems are often expensive because they require:

* GPS trackers
* Wearable sensors
* Multiple cameras
* Professional tracking software
* Manual analysis

This makes performance analytics difficult to access for students, grassroots teams, academies, coaches, and football enthusiasts.

PitchTrack aims to provide basic player movement analytics using an ordinary pre-recorded football video.

The user should be able to upload a video and receive meaningful player statistics without manually tracking every player.

---

## 3. Product Vision

The vision of PitchTrack is:

> Turn an ordinary football video into useful player movement statistics using Computer Vision.

The application should hide the complexity of the Computer Vision pipeline from the user.

The user does not need to understand:

* YOLO
* ByteTrack
* K-Means
* Optical Flow
* Perspective Transformation

They simply upload a video and view the results.

---

## 4. Product Goals

**G1 — Simple Video Analysis**
Allow the user to upload a football video and start analysis with minimal interaction.

**G2 — Automated Player Tracking**
Automatically detect and track players throughout the video.

**G3 — Team Classification**
Automatically group players into Team A and Team B using jersey-color information.

**G4 — Movement Analytics**
Calculate:

* Average speed
* Minimum speed
* Maximum speed
* Total distance covered

**G5 — Visual Analysis**
Show player tracking directly over the video.

**G6 — No Database for Initial MVP**
Keep the initial system simple by avoiding a database unless one becomes technically necessary.

---

## 5. Product Scope

### 5.1 Included in Initial MVP

The MVP will contain:

* Video upload
* Video validation
* Video processing
* Player detection
* Player tracking
* Team classification
* Ball detection/tracking
* Camera movement compensation
* Perspective transformation
* Speed calculation
* Distance calculation
* Player statistics
* Video playback
* Tracking overlays
* Basic filtering
* CSV export
* JSON export

---

## 6. Explicitly Out of Scope

The following features will NOT be implemented in the initial version.

**Live Video**

No:

* Webcam
* Live camera
* RTMP stream
* Live match analysis
* Screen recording

PitchTrack is strictly an upload-only application.

**Player Identity Recognition**

The system will not automatically identify:

* Player names
* Faces
* Jersey numbers

Players will initially be represented using tracking IDs.

Example:

```
Player 1
Player 2
Player 3
Player 4
```

Manual labels can be considered later.

**Tactical Analysis**

Not included:

* Pass detection
* Shot detection
* Goal detection
* Offside detection
* Formation detection
* Tactical events

**Multi-Camera Analysis**

Only a single video source is supported initially.

---

## 7. Target Users

### 7.1 Football Coaches

A coach can upload a training session and review player movement.

### 7.2 Football Analysts

An analyst can use the system to study player speed and distance.

### 7.3 Students

Students can use the application as a practical Computer Vision project.

### 7.4 Football Enthusiasts

Users interested in football analytics can experiment with match footage.

---

## 8. Core User Flow

The initial user flow should be extremely simple.

```
Open PitchTrack
        ↓
Upload Video
        ↓
Validate Video
        ↓
Start Processing
        ↓
Computer Vision Pipeline
        ↓
Generate Results
        ↓
Analysis Dashboard
        ↓
View Player Statistics
        ↓
Export Results
```

There is no requirement for registration or login in the initial MVP.

---

## 9. Functional Requirements

### 9.1 Video Upload

The system shall allow the user to upload a pre-recorded football video.

Supported formats:

* MP4
* MOV
* AVI

Preferred codec:

* H.264
* H.265

The upload interface shall provide:

* Drag-and-drop
* Browse button
* File name
* File size
* Upload progress
* Validation message

### 9.2 Video Validation

Before processing, the system should validate:

* File format
* File size
* Video duration
* Video readability
* Frame rate
* Resolution

Example error:

```
Unable to process this video.
Reason:
Unsupported or corrupted video file.
```

### 9.3 Video Processing

Once a valid video is uploaded, the system starts the Computer Vision pipeline.

The processing status should be visible to the user.

Possible states:

```
Uploaded
   ↓
Processing
   ↓
Completed
```

or

```
Uploaded
   ↓
Processing
   ↓
Failed
```

---

## 10. Computer Vision Pipeline

The primary processing pipeline is:

```
Input Video
     ↓
Frame Extraction
     ↓
YOLOv8 Detection
     ↓
ByteTrack Tracking
     ↓
Team Classification
     ↓
Ball Detection
     ↓
Ball Position Interpolation
     ↓
Optical Flow
     ↓
Camera Motion Compensation
     ↓
Perspective Transformation
     ↓
Pixel → Meter Conversion
     ↓
Speed Calculation
     ↓
Distance Calculation
     ↓
Statistics Generation
     ↓
Annotated Video
```

---

## 11. Player Detection

YOLOv8 will be used to detect objects within each video frame.

The system should identify:

* Players
* Ball
* Referee, where detection/classification allows

Each detected player will receive a tracking ID.

Example:

```
Frame 100
Player 1
Player 2
Player 5
Player 8
```

---

## 12. Player Tracking

ByteTrack will associate player detections between consecutive frames.

Example:

```
Frame 100 → Player 5
Frame 101 → Player 5
Frame 102 → Player 5
Frame 103 → Player 5
```

This allows the system to construct a movement path for each player.

---

## 13. Team Classification

The system will use K-Means clustering to classify players based on visual jersey/color information.

The initial output will be:

```
Team A
Team B
```

The system should not depend solely on color in the user interface.

Team indicators should also contain:

* Team label
* Marker shape

---

## 14. Ball Tracking

The system will detect the football where possible.

When the ball is temporarily not detected, the pipeline may interpolate its position.

Ball data is primarily used for visualization in the initial MVP.

---

## 15. Camera Motion Compensation

Optical Flow will be used to estimate camera movement.

This helps distinguish:

```
Camera movement
```

from:

```
Player movement
```

This is important when calculating player speed and distance.

---

## 16. Perspective Transformation

The system will transform image coordinates into approximate real-world field coordinates.

Conceptually:

```
Pixel Coordinates
       ↓
Perspective Transform
       ↓
Field Coordinates in Meters
```

The transformed coordinates will be used for speed and distance calculations.

---

## 17. Speed Calculation

For each tracked player, the system will calculate speed from movement between consecutive positions.

The dashboard shall display:

* Minimum speed
* Maximum speed
* Average speed

Speed shall be displayed in:

```
km/h
```

---

## 18. Distance Calculation

The system shall calculate the total distance travelled by each player.

Example:

```
Player 1
Distance: 8,420 m
```

Distance shall be displayed in:

```
meters
```

and optionally:

```
kilometers
```

---

## 19. Analysis Dashboard

After processing is complete, the user will be taken to the Analysis Workspace.

The dashboard shall contain:

**Video Player**
Shows the original video.

**Tracking Overlay**
Shows:

* Player markers
* Player IDs
* Team indicators
* Ball marker
* Referee marker

**Player Statistics**

Example:

| Player   | Team   | Avg Speed | Min Speed | Max Speed | Distance |
| -------- | ------ | --------- | --------- | --------- | -------- |
| Player 1 | Team A | 8.4 km/h  | 0.2 km/h  | 26.4 km/h | 8,420 m  |
| Player 2 | Team A | 7.9 km/h  | 0.1 km/h  | 24.8 km/h | 7,930 m  |
| Player 3 | Team B | 8.8 km/h  | 0.3 km/h  | 27.1 km/h | 8,750 m  |

---

## 20. Tracker Controls

The user shall be able to:

* Play
* Pause
* Seek
* Change playback speed
* Step through frames

Playback speeds:

```
0.5x
1x
2x
```

---

## 21. Overlay Controls

The user can enable or disable:

```
☑ Players
☑ Player IDs
☑ Ball
☑ Referee
```

This allows the user to customize the visualization.

---

## 22. Player Selection

Selecting a player in the dashboard should highlight that player in the video.

Example:

```
Click Player 7
        ↓
Player 7 highlighted in dashboard
        ↓
Player 7 highlighted in video
```

This creates a connection between the visual tracking and numerical statistics.

---

## 23. Team Filtering

The dashboard shall support:

```
All
Team A
Team B
```

Selecting a team should update:

* Player list
* Video overlay

---

## 24. Player Filtering

The user can search for a specific tracking ID.

Example:

```
Search: Player 12
```

Only Player 12 will be displayed/highlighted.

---

## 25. Time Filtering

The dashboard should support selecting a time window.

Example:

```
00:00 ─────────────── 90:00
        45:00 ─ 60:00
```

Statistics should be calculated for the selected period.

Example:

```
Full Match
Average Speed: 8.4 km/h
Distance: 8,420 m
```

versus:

```
45–60 minutes
Average Speed: 9.1 km/h
Distance: 1,320 m
```

---

## 26. Export

The user shall be able to export analysis results.

**CSV**

Example:

```
Player,Team,Average Speed,Min Speed,Max Speed,Distance
Player 1,Team A,8.4,0.2,26.4,8420
```

**JSON**

Structured machine-readable output.

**Annotated Video**

The system may generate an MP4 containing tracking overlays.

---

## 27. File-Based Storage — Initial MVP

The initial version will intentionally avoid a database.

A simple directory structure will be used.

Example:

```
pitchtrack/
├── app/
│   ├── frontend/
│   ├── backend/
│   └── pipeline/
│
├── uploads/
│   ├── match_001.mp4
│   └── training_001.mp4
│
├── results/
│   ├── match_001/
│   │   ├── players.json
│   │   ├── positions.json
│   │   ├── statistics.json
│   │   └── annotated.mp4
│   │
│   └── training_001/
│       ├── players.json
│       ├── positions.json
│       ├── statistics.json
│       └── annotated.mp4
│
└── temp/
```

---

## 28. JSON-Based Result Storage

Instead of a database, the system will initially store analysis results as JSON.

Example:

```json
{
  "video": {
    "filename": "match_001.mp4",
    "duration": 5400,
    "fps": 30
  },
  "players": [
    {
      "tracking_id": 1,
      "team": "Team A",
      "average_speed_kmh": 8.4,
      "minimum_speed_kmh": 0.2,
      "maximum_speed_kmh": 26.4,
      "total_distance_m": 8420
    }
  ]
}
```

The frontend can request this data from the backend.

---

## 29. Why No Database Initially?

The initial application does not require a database because:

* There is no mandatory user registration.
* There is no multi-user account system.
* Videos can be stored locally.
* Analysis results can be stored as JSON.
* The application is initially intended as an MVP/prototype.
* There is no requirement for complex relational queries.
* The Computer Vision pipeline is the primary focus.

This reduces:

* Development complexity
* Setup time
* Infrastructure requirements
* Debugging effort

---

## 30. Database Introduction Criteria

A database should only be introduced when one or more of the following become necessary:

* Multiple user accounts
* Persistent user history
* Large numbers of videos
* Cloud deployment
* Multiple workers
* Job queue persistence
* Advanced search
* User permissions
* Subscription plans
* Long-term analytics storage

At that point, the project will move to a Django-based backend/database architecture.

---

## 31. Django Fallback Architecture

If file-based storage becomes insufficient:

```
React Frontend
        ↓
Django Backend
        ↓
Django ORM
        ↓
Database
        ↓
Video Storage
```

Django would manage:

* Users
* Videos
* Processing jobs
* Players
* Teams
* Statistics
* Exports

The Computer Vision pipeline would remain independent from the database layer.

---

## 32. Initial Technical Architecture

The recommended initial architecture is:

```
                 ┌─────────────────┐
                 │      User       │
                 └────────┬────────┘
                          │
                          ↓
                 ┌─────────────────┐
                 │    Frontend     │
                 │ React / HTML    │
                 └────────┬────────┘
                          │
                          ↓
                 ┌─────────────────┐
                 │     Backend     │
                 │     Python      │
                 └────────┬────────┘
                          │
             ┌────────────┴────────────┐
             ↓                         ↓
      ┌──────────────┐         ┌──────────────┐
      │ Video Files  │         │ JSON Results │
      └──────────────┘         └──────────────┘
             │                         │
             └────────────┬────────────┘
                          ↓
                 ┌─────────────────┐
                 │ CV Processing   │
                 │ YOLOv8          │
                 │ ByteTrack       │
                 │ OpenCV          │
                 │ K-Means         │
                 └─────────────────┘
```

---

## 33. Suggested Technology Stack

**Frontend**

Initial option:

* HTML
* CSS
* JavaScript

or:

* React
* JavaScript/TypeScript

The frontend should remain lightweight initially.

**Backend**

Python-based backend.

Recommended:

* FastAPI

Alternative if database requirements emerge:

* Django

**Computer Vision**

* Python
* OpenCV
* YOLOv8
* ByteTrack
* NumPy
* Scikit-learn

**Storage**

Initial:

* Local filesystem
* JSON

Later:

* Django ORM
* SQLite/PostgreSQL depending on scale

---

## 34. Processing Architecture

For the initial MVP, processing can be performed as a background task.

```
Upload
↓
Save Video
↓
Start Processing
↓
Run CV Pipeline
↓
Generate JSON
↓
Generate Annotated Video
↓
Mark Processing Complete
↓
Display Results
```

For larger deployments, this can later become:

```
Upload
↓
Job Queue
↓
GPU Worker
↓
Processing
↓
Database/Object Storage
```

---

## 35. Error Handling

The system shall handle:

**Invalid Video**

```
The uploaded file could not be read.
```

**Unsupported Format**

```
This video format is not supported.
```

**Processing Failure**

```
Video processing failed.
Please try processing the video again.
```

**Insufficient Detection**

```
Unable to reliably detect players in this video.
Try using a clearer video with better lighting and visibility.
```

**Perspective Calibration Failure**

```
Unable to calculate reliable field coordinates.
```

---

## 36. Performance Requirements

The system does not require real-time processing.

The primary goal is batch processing.

Target:

```
Processing time should ideally approach the duration of the uploaded video
when using suitable GPU hardware.
```

Example:

```
10-minute video
Target:
Approximately 10–15 minutes processing
```

This is a target rather than a guaranteed requirement because processing time depends on:

* GPU
* Resolution
* FPS
* Number of players
* Detection model
* Video quality

---

## 37. Hardware Requirements

Computer Vision processing is expected to benefit significantly from GPU acceleration.

Development may use:

* NVIDIA GPU
* Apple Silicon GPU where supported
* CPU fallback

The system should automatically select the available processing device where practical.

---

## 38. Security Requirements

Even without a database, the application shall:

* Validate uploaded files
* Restrict file types
* Restrict file sizes
* Prevent arbitrary file execution
* Store uploaded files outside executable directories where possible
* Prevent unauthorized access to uploaded videos

---

## 39. Privacy

Uploaded football videos may contain identifiable individuals.

The application should:

* Clearly state that users must have permission to upload footage.
* Avoid facial recognition.
* Use anonymous tracking IDs.
* Allow users to delete uploaded videos.
* Delete associated generated files when the video is deleted.

Example:

```
Delete Video
↓
Delete Original Video
↓
Delete JSON Results
↓
Delete Tracking Data
↓
Delete Annotated Video
```

---

## 40. UI Screens

**Screen 1 — Home**

Contains:

* PitchTrack name
* Product description
* Upload Video button

**Screen 2 — Upload**

Contains:

* Drag-and-drop area
* Browse button
* File information
* Upload progress

**Screen 3 — Processing**

Contains:

```
Processing Video...
████████████░░░░░░

Player Detection      ✓
Player Tracking       ✓
Team Classification   Running...
Speed Calculation     Waiting...
```

**Screen 4 — Analysis Workspace**

Main application screen.

Contains:

* Left: Video player and tracking overlay.
* Right: Player statistics.
* Top: Team filters and overlay controls.
* Bottom: Timeline/time-range controls.

**Screen 5 — Export**

Options:

```
Export Statistics
☐ CSV
☐ JSON
☐ Annotated Video
```

---

## 41. Acceptance Criteria

**Upload**

Given a supported video:

```
User uploads video
        ↓
File is accepted
        ↓
Processing begins
```

**Processing**

Given a valid video:

```
Video
 ↓
CV Pipeline
 ↓
Results
```

The system must produce player tracking and analytics when detection succeeds.

**Dashboard**

When processing is complete, the dashboard must display:

* Player ID
* Team
* Average speed
* Minimum speed
* Maximum speed
* Distance

**Tracking**

Player tracking IDs should remain consistent across frames where the tracking algorithm successfully maintains identity.

**Filtering**

Changing the team, player, or time-range filter must update the displayed statistics and relevant overlays.

**Export**

Exported CSV/JSON values must correspond to the selected analysis scope.

**No Live Capture**

The application must not contain:

* Webcam button
* Record button
* Live stream button
* RTMP input

The only video ingestion method is file upload.

---

## 42. MVP Development Plan

### Phase 1 — Computer Vision Pipeline

Goal: Make the existing pipeline work reliably on a test video.

Tasks:

* YOLOv8 detection
* ByteTrack tracking
* Team classification
* Ball tracking
* Optical flow
* Perspective transformation
* Speed calculation
* Distance calculation

Deliverable:

A Python pipeline that takes:

```
input.mp4
```

and produces:

```
annotated.mp4
statistics.json
positions.json
```

---

## 43. Phase 2 — Backend

Build the upload and processing API.

Tasks:

* Upload endpoint
* Video validation
* File storage
* Start processing
* Processing status
* Results endpoint
* Export endpoints

No database.

---

## 44. Phase 3 — Frontend

Build:

* Upload page
* Processing page
* Analysis page
* Video player
* Tracking overlay
* Player dashboard
* Filters

---

## 45. Phase 4 — Integration

Connect:

```
Frontend
↓
Backend
↓
CV Pipeline
↓
JSON Results
↓
Dashboard
```

Test the complete workflow.

---

## 46. Phase 5 — Export and Testing

Implement:

* CSV export
* JSON export
* Annotated video export
* Error handling
* Performance testing
* UI testing

---

## 47. Phase 6 — Database Decision

After the MVP has been tested, evaluate whether a database is actually necessary.

**If NO**

Continue with:

```
Filesystem + JSON
```

**If YES**

Introduce:

```
Django
+
Django ORM
+
Database
```

The Computer Vision pipeline should not need to be rewritten.

---

## 48. Future Roadmap

Once the MVP is stable, possible future features include:

**Version 2**

* Player heatmaps
* Speed zones
* Sprint detection
* Acceleration/deceleration
* Player comparison
* Improved calibration

**Version 3**

* Jersey-number recognition
* Manual player identification
* Match reports
* Tactical analysis
* Possession analysis

**Version 4**

* Multi-camera support
* Cloud processing
* User accounts
* Team management
* Historical match comparison

**Possible Future Version**

* Live video analysis

However, live video is explicitly not part of the current product.

---

## 49. Success Metrics

The MVP will be considered successful when:

* A user can upload a football video without technical knowledge.
* The video can be processed automatically.
* Players can be tracked.
* Teams can be differentiated.
* Player speed can be calculated.
* Player distance can be calculated.
* Results are displayed in a web dashboard.
* Results can be exported.
* The system works without requiring a database.

---

## 50. Final Product Definition

The first version of PitchTrack should be understood as:

> A web application that accepts a pre-recorded football video, runs an existing Computer Vision pipeline, and presents player tracking, speed, distance, team classification, and visual analytics through a browser.

The project should not begin with authentication, subscriptions, cloud infrastructure, PostgreSQL, or complex database architecture.

The recommended development order is:

```
1. Make CV Pipeline Work
             ↓
2. Produce JSON + Annotated Video
             ↓
3. Build Python Backend
             ↓
4. Add Video Upload
             ↓
5. Add Processing Status
             ↓
6. Build Web Dashboard
             ↓
7. Connect Dashboard to Results
             ↓
8. Add Filters
             ↓
9. Add Export
             ↓
10. Test Complete MVP
             ↓
11. Evaluate Need for Database
             ↓
       ┌─────┴─────┐
       ↓           ↓
     NO            YES
       ↓           ↓
 Files + JSON   Django + DB
```

The database is therefore a scalability decision, not an MVP prerequisite.
