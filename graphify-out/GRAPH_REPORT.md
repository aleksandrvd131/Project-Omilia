# Graph Report - Project-Omilia  (2026-11-22)

## Corpus Check
- 74 files · ~60,508 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 7 file(s) not represented in the graph (top: (none) 5, .css 1, .lock 1)

## Summary
- 907 nodes · 1820 edges · 48 communities (40 shown, 8 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 180 edges (avg confidence: 0.87)
- Token cost: 2,400 input · 1,650 output

## Community Hubs (Navigation)
- Dynamic Gestures & Biomechanics
- Automated Testing & CI Suite
- GitHub Actions CI Pipeline
- Blitz Quizzes & k-NN Scoring
- Real-Time WebSocket Inference
- Model Serving & ONNX Metadata
- GitHub Actions CD Deployment
- FastAPI App & Architecture Refactoring
- Dynamic DTW Gesture Service
- Biometric Diagnostics & Quality Feedback
- Frontend Application Orchestrator
- Motion Segmentation & Frontend Assets
- Slovo Dataset Canonical Synthesis
- Slovo Landmark Definitions
- Gesture Catalog REST API
- Spatial Invariance & Augmentation
- In-Browser ONNX Classifier
- SQLite Dataset Migration & Queries
- Frontend Modules Unit Tests
- Gamification & Blitz Mode
- Pose Biometrics & Hand Diagnostics
- Camera Subsystem & Glassmorphism HUD
- User Authentication & Session API
- Frontend Startup Lifecycle Tests
- CommonJS Diagnostics Test Suite
- Gesture Catalog Database Access
- Server Lifespan & Service Dependencies
- Password Hashing & Security Architecture
- Role-Based Access Control & RBAC
- Frontend UI Components & XP System
- Gesture Catalog & Curriculum View
- Dynamic Clip Segmentation Tests
- PWA Web App Manifest
- Slovo RSL Dataset Database Tests
- Warmup Session & Interval Review
- Database Schema Migrations & Seeding
- Daily Warmup & Spaced Repetition API
- Dataset Export & Ghost Silhouettes
- Interactive Practice & Learning Modal
- Text-to-Speech Audio Synthesis API
- Full Dataset Serialization & Transfer
- SuperMemo-2 Spaced Repetition Algorithm
- Static Gesture Sample Queries
- Dataset Export-Import Roundtrip Tests
- Service Worker Cache & PWA Assets

## God Nodes (most connected - your core abstractions)
1. `StaticGestureServer` - 33 edges
2. `get_connection()` - 31 edges
3. `DynamicGestureServer` - 21 edges
4. `create_app()` - 20 edges
5. `Pose` - 19 edges
6. `bindEvents()` - 18 edges
7. `StaticGesture` - 17 edges
8. `DynamicGestures` - 15 edges
9. `api_get_gestures()` - 14 edges
10. `renderCatalog()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `k-NN Distance-Weighted Confidence Scoring` --implements--> `StaticGestureServer`  [EXTRACTED]
  IMPROVEMENT_PLAN.md → src/project_omilia/services/static_service.py
- `RBAC Role-Based Access Control` --implements--> `require_admin_user()`  [EXTRACTED]
  IMPROVEMENT_PLAN.md → src/project_omilia/api/deps.py
- `Phase 3: Backend Architectural Refactoring` --references--> `DynamicGestureServer`  [EXTRACTED]
  IMPROVEMENT_PLAN.md → src/project_omilia/services/dynamic_service.py
- `Phase 3: Backend Architectural Refactoring` --references--> `StaticGestureServer`  [EXTRACTED]
  IMPROVEMENT_PLAN.md → src/project_omilia/services/static_service.py
- `Scrypt Password Hashing with Salt & Digest` --implements--> `hash_password()`  [EXTRACTED]
  IMPROVEMENT_PLAN.md → src/project_omilia/db.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Clean Backend Modular Refactoring Layers** — src_project_omilia_app_create_app, src_project_omilia_api_deps_require_admin_user, src_project_omilia_services_static_service_staticgestureserver, src_project_omilia_services_dynamic_service_dynamicgestureserver, improvement_plan_phase3_modular_backend [EXTRACTED 1.00]
- **Hardened Authentication and RBAC Security Suite** — src_project_omilia_db_hash_password, src_project_omilia_api_deps_require_admin_user, improvement_plan_scrypt_password_hashing, improvement_plan_rbac_access_control [EXTRACTED 1.00]
- **Zero-Latency Client-Side ONNX Inference Pipeline** — src_project_omilia_ml_onnx_exporter, src_project_omilia_api_models_get_static_onnx_model, src_project_omilia_frontend_index_pwa, improvement_plan_client_side_onnx_inference [INFERRED 0.95]

## Communities (48 total, 8 thin omitted)

### Community 0 - "Dynamic Gestures & Biomechanics"
Cohesion: 0.06
Nodes (19): Adaptive Dynamic Gesture Thresholds, Hand, Pose, is_right_hand(), DatasetNotFoundError, IncorrectDataError, JSONDatasetError, OmiliaError (+11 more)

### Community 1 - "Automated Testing & CI Suite"
Cohesion: 0.06
Nodes (19): Phase 6: Testing, CI/CD and Containerization, test_session_expiration(), test_user_registration_roles_and_sessions(), test_legacy_sha256_password_migration(), test_user_registration_and_login_flow(), test_learned_gestures_persistence(), test_sqlite_gestures_crud(), test_static_samples_blob_serialization() (+11 more)

### Community 2 - "GitHub Actions CI Pipeline"
Cohesion: 0.06
Nodes (40): name, needs, runs-on, steps, jobs, docker-build, lint, test (+32 more)

### Community 3 - "Blitz Quizzes & k-NN Scoring"
Cohesion: 0.10
Nodes (11): k-NN Distance-Weighted Confidence Scoring, api_blitz_questions(), api_delete_gesture(), api_get_gestures(), api_import_dataset(), gesture_ws(), Developer & Diagnostic Dashboard, StaticGestureServer (+3 more)

### Community 4 - "Real-Time WebSocket Inference"
Cohesion: 0.08
Nodes (9): dtw_distance(), get_curriculum_level(), main(), test_import_endpoint_validation(), test_ui_debug_html_export_import(), test_fast_dtw_distance(), test_optimized_math_functions(), test_curriculum_definitions_and_level_mapping() (+1 more)

### Community 5 - "Model Serving & ONNX Metadata"
Cohesion: 0.12
Nodes (19): Client-Side In-Browser ONNX Inference (0ms), get_static_classifier_metadata(), get_static_onnx_model(), _attribute_float(), _attribute_int(), _build_onnx_model_bytes(), export_classifier_metadata(), export_onnx_model_bytes() (+11 more)

### Community 6 - "GitHub Actions CD Deployment"
Cohesion: 0.06
Nodes (31): env, IMAGE_NAME, REGISTRY, jobs, publish-container, name, on, push (+23 more)

### Community 7 - "FastAPI App & Architecture Refactoring"
Cohesion: 0.09
Nodes (10): Phase 3: Backend Architectural Refactoring, project-omilia, create_app(), test_api_endpoints(), test_gesture_silhouette_endpoints(), client(), test_index_html_pwa_meta_and_sw(), test_manifest_endpoint() (+2 more)

### Community 8 - "Dynamic DTW Gesture Service"
Cohesion: 0.10
Nodes (11): Phase 4: ML & CV Modernization, Vectorized Fast-DTW (6.2x Speedup), dtw_distance(), sakoe_chiba_dtw(), test_dynamic_gesture_server_dtw_integration(), test_frontend_motion_vad_node_suite(), test_sakoe_chiba_dtw_identity(), test_sakoe_chiba_dtw_symmetry() (+3 more)

### Community 9 - "Biometric Diagnostics & Quality Feedback"
Cohesion: 0.12
Nodes (5): recording_card(), make_pose(), import_static_datasets(), _generate_synthetic_hand_landmarks(), test_hand_scale_invariance()

### Community 10 - "Frontend Application Orchestrator"
Cohesion: 0.24
Nodes (26): abortWarmupSession(), bindEvents(), checkAuth(), closeOnboarding(), closePracticeModal(), closeTutorialModal(), endDynamicAttempt(), ensureWebSocket() (+18 more)

### Community 11 - "Motion Segmentation & Frontend Assets"
Cohesion: 0.11
Nodes (17): Concept and Goals of Modernization, Project Omiλia RSL Platform, detectMotionSegment(), estimateWristVelocity(), hasLandmarks(), hasValidHand(), nearestFrame(), replaceMissingFrame() (+9 more)

### Community 12 - "Slovo Dataset Canonical Synthesis"
Cohesion: 0.13
Nodes (9): build_db_records(), build_gesture_metadata_records(), generate_augmented_samples(), generate_canonical_vector(), _norm_vec(), test_slovo_db_records_generation(), test_slovo_feature_vectors_dimensions_and_finiteness(), test_slovo_knn_classification_with_augmentation() (+1 more)

### Community 13 - "Slovo Landmark Definitions"
Cohesion: 0.10
Nodes (10): build_hand_landmarks(), _build_slovo_definitions(), get_all_slovo_gestures(), get_all_slovo_landmarks(), get_slovo_gesture(), get_slovo_landmarks(), SlovoGestureDefinition, _build_additional_canonical_landmarks() (+2 more)

### Community 14 - "Gesture Catalog REST API"
Cohesion: 0.14
Nodes (9): api_learn_gesture(), api_review_gesture(), api_save_gesture(), ReviewRequest, DatasetImportPayload, GestureCard, GestureImportItem, LearnRequest (+1 more)

### Community 15 - "Spatial Invariance & Augmentation"
Cohesion: 0.14
Nodes (10): scalar_to_vec(), augment_static_samples(), augment_static_vector(), process_hand(), _rotate_and_scale_vec3(), _rotate_normal(), test_dtw(), test_import_endpoint_and_model_reload() (+2 more)

### Community 16 - "In-Browser ONNX Classifier"
Cohesion: 0.11
Nodes (3): HandFeatureProcessor, OmiliaFeatureExtractor, OmiliaStaticClassifier

### Community 17 - "SQLite Dataset Migration & Queries"
Cohesion: 0.15
Nodes (15): SQLite Dataset Migration & features_blob, count_dynamic_samples(), delete_gesture(), delete_static_gesture(), get_connection(), get_dynamic_samples(), get_learned_gestures(), get_user_by_token() (+7 more)

### Community 18 - "Frontend Modules Unit Tests"
Cohesion: 0.10
Nodes (4): assert, fs, path, test

### Community 19 - "Gamification & Blitz Mode"
Cohesion: 0.13
Nodes (12): Phase 7: Methodology & Gamification (SM-2 / Streaks), abortBlitz(), completeBlitzQuestion(), finishBlitz(), handleBlitzPrediction(), loadBlitzQuestion(), setupBlitzIntro(), startBlitz() (+4 more)

### Community 20 - "Pose Biometrics & Hand Diagnostics"
Cohesion: 0.14
Nodes (8): _diagnose_hand(), diagnose_static_gesture(), _create_base_vector(), test_diagnose_finger_bend(), test_diagnose_finger_straighten(), test_diagnose_hand_position_height(), test_diagnose_matching_gesture(), test_diagnose_palm_orientation_turn_to_camera()

### Community 21 - "Camera Subsystem & Glassmorphism HUD"
Cohesion: 0.19
Nodes (14): Camera HUD Glassmorphism & Feedback, Phase 1: Critical Vulnerabilities & Git Cleanup, checkHandAlignment(), clearCameraError(), drawGhostSilhouette(), formatCameraError(), getAvailableVideoInputs(), getFacingMode() (+6 more)

### Community 22 - "User Authentication & Session API"
Cohesion: 0.16
Nodes (6): api_login(), api_logout(), api_me(), api_register(), AuthRequest, UserResponse

### Community 23 - "Frontend Startup Lifecycle Tests"
Cohesion: 0.12
Nodes (10): assert, createElement(), element(), frontend, fs, html, path, scripts (+2 more)

### Community 24 - "CommonJS Diagnostics Test Suite"
Cohesion: 0.14
Nodes (8): assert, OmiliaInference, path, test, assert, OmiliaInference, path, test

### Community 25 - "Gesture Catalog Database Access"
Cohesion: 0.14
Nodes (3): get_all_gestures(), get_gesture(), SM2Result

### Community 26 - "Server Lifespan & Service Dependencies"
Cohesion: 0.19
Nodes (3): get_dynamic_server(), lifespan(), DynamicGestureServer

### Community 27 - "Password Hashing & Security Architecture"
Cohesion: 0.21
Nodes (7): Phase 2: Auth and Security Architecture, Scrypt Password Hashing with Salt & Digest, hash_password(), _hash_password(), login_user(), register_user(), verify_password()

### Community 28 - "Role-Based Access Control & RBAC"
Cohesion: 0.23
Nodes (6): RBAC Role-Based Access Control, get_current_user_from_request(), get_static_server(), get_token_from_request(), require_admin_user(), require_current_user()

### Community 29 - "Frontend UI Components & XP System"
Cohesion: 0.34
Nodes (11): addExtraXP(), apiFetch(), calculateUserXP(), computeAchievements(), escapeHtml(), getStreakValue(), renderAchievements(), safeLocalStorageGet() (+3 more)

### Community 30 - "Gesture Catalog & Curriculum View"
Cohesion: 0.40
Nodes (12): Phase 5: Frontend, UI & UX Modernization, calculateLevelStats(), ensureCatalogStyles(), ensureCurriculumDOM(), getFilteredGestures(), getGestureLevelInfo(), loadCatalog(), renderCatalog() (+4 more)

### Community 31 - "Dynamic Clip Segmentation Tests"
Cohesion: 0.18
Nodes (10): assert, clip(), frame(), fs, landmarks(), path, source, test (+2 more)

### Community 32 - "PWA Web App Manifest"
Cohesion: 0.17
Nodes (11): background_color, categories, description, display, icons, name, orientation, scope (+3 more)

### Community 33 - "Slovo RSL Dataset Database Tests"
Cohesion: 0.17
Nodes (5): setup_module(), test_slovo_gestures_in_sqlite_db(), test_slovo_samples_in_sqlite_db(), test_sqlite_datasets_consistency(), test_static_gesture_models_reload_and_classification()

### Community 34 - "Warmup Session & Interval Review"
Cohesion: 0.31
Nodes (8): advanceWarmup(), completeWarmupStep(), createWarmupState(), fetchWarmupQueue(), finishWarmup(), handleWarmupPrediction(), renderWarmupStep(), startWarmup()

### Community 35 - "Database Schema Migrations & Seeding"
Cohesion: 0.22
Nodes (6): init_db(), insert_static_samples(), _insert_static_samples(), upsert_gesture(), _upsert_gesture(), get_curriculum_info()

### Community 36 - "Daily Warmup & Spaced Repetition API"
Cohesion: 0.22
Nodes (4): api_get_warmup(), get_daily_warmup(), get_user_streak(), _parse_date()

### Community 37 - "Dataset Export & Ghost Silhouettes"
Cohesion: 0.20
Nodes (4): api_export_dataset(), api_get_gesture_card(), api_get_gesture_silhouette(), get_gesture_silhouette()

### Community 38 - "Interactive Practice & Learning Modal"
Cohesion: 0.28
Nodes (4): closeTutorialModal(), handlePracticePrediction(), onGestureSuccessfullyLearned(), openPracticeModal()

### Community 40 - "Full Dataset Serialization & Transfer"
Cohesion: 0.29
Nodes (3): export_dataset(), import_dataset(), test_export_endpoint()

## Knowledge Gaps
- **103 isolated node(s):** `name`, `tags`, `workflow_dispatch`, `REGISTRY`, `IMAGE_NAME` (+98 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 403 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `StaticGestureServer` connect `Blitz Quizzes & k-NN Scoring` to `Dynamic Gestures & Biomechanics`?**
  _High betweenness centrality (0.004) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `StaticGestureServer` (e.g. with `Pose` and `StaticGesture`) actually correct?**
  _`StaticGestureServer` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `name`, `tags`, `workflow_dispatch` to the rest of the system?**
  _103 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Dynamic Gestures & Biomechanics` be split into smaller, more focused modules?**
  _Cohesion score 0.05576923076923077 - nodes in this community are weakly interconnected._
- **Why does `lifespan()` connect `Server Lifespan & Service Dependencies` to `Blitz Quizzes & k-NN Scoring`, `Database Schema Migrations & Seeding`?**
  _High betweenness centrality (0.003) - this node is a cross-community bridge._
- **Should `Automated Testing & CI Suite` be split into smaller, more focused modules?**
  _Cohesion score 0.06060606060606061 - nodes in this community are weakly interconnected._
- **Why does `create_app()` connect `FastAPI App & Architecture Refactoring` to `Server Lifespan & Service Dependencies`?**
  _High betweenness centrality (0.003) - this node is a cross-community bridge._