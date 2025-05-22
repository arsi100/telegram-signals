# Google Cloud Function Deployment Guide (Cloud Build & GitHub)

This document outlines the steps taken to successfully deploy the Python Cloud Function from the `functions` directory using Cloud Build triggered by pushes to the `main` GitHub branch. It includes troubleshooting steps encountered and resolved during the process, reflecting the journey to a stable deployment.

## 1. Prerequisites

*   Google Cloud Project created (`telegram-signals-205cc`).
*   Billing enabled on the project.
*   GitHub repository (`arsi100/telegram-signals`) connected to the Google Cloud project.
*   Required APIs enabled (Cloud Build, Cloud Functions, Cloud Scheduler, Secret Manager, IAM, Artifact Registry, Cloud Logging, Cloud Firestore, Cloud Run).
    ```bash
    # Example commands (run for others as needed)
    gcloud services enable cloudbuild.googleapis.com --project=telegram-signals-205cc
    gcloud services enable cloudfunctions.googleapis.com --project=telegram-signals-205cc
    gcloud services enable cloudscheduler.googleapis.com --project=telegram-signals-205cc
    gcloud services enable secretmanager.googleapis.com --project=telegram-signals-205cc
    gcloud services enable iam.googleapis.com --project=telegram-signals-205cc
    gcloud services enable artifactregistry.googleapis.com --project=telegram-signals-205cc
    gcloud services enable logging.googleapis.com --project=telegram-signals-205cc
    gcloud services enable firestore.googleapis.com --project=telegram-signals-205cc
    gcloud services enable run.googleapis.com --project=telegram-signals-205cc # For 2nd Gen Functions
    ```

## 2. Secret Management

*   API keys and sensitive configuration (e.g., `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `CRYPTOCOMPARE_API_KEY`) were stored in Google Secret Manager within the project.
*   Ensure secrets are created with appropriate names.
*   **Important for Telegram:** If a bot token is compromised or behaving unexpectedly, revoke it on Telegram via BotFather, generate a new one, and update the secret in GCP Secret Manager. The function will pick up the new secret on the next deployment/revision.

## 3. Cloud Build Trigger Setup

*   A Cloud Build trigger was created to watch the `main` branch of the connected GitHub repository.
*   **Trigger Service Account:** The trigger was configured to use the default Cloud Build service account (`[PROJECT_NUMBER]@cloudbuild.gserviceaccount.com`).
*   **Build Configuration:** The trigger was configured to use the `cloudbuild.yaml` file from the repository.

## 4. `cloudbuild.yaml` Configuration

This file defines the build steps. The key step deploys the Cloud Function:

```yaml
steps:
- name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
  args:
  - gcloud
  - functions
  - deploy
  - run-signal-generation # Function name
  - --gen2 # Specify 2nd Generation Function
  - --runtime=python311 # Match Python version in requirements.txt
  - --region=us-central1 # Target region for the function
  - --source=./functions # Directory containing function code and requirements.txt
  - --entry-point=run_signal_generation # Python function to execute
  - --trigger-http # Publicly invokable via HTTP (for Scheduler)
  # --no-allow-unauthenticated # Initially used, but switched to --allow-unauthenticated for simplicity with Scheduler.
  # If using --no-allow-unauthenticated, OIDC setup for Scheduler is critical.
  - --allow-unauthenticated # Allows invocation without OIDC setup for Scheduler, ensure function has other security if needed.
  - --service-account= # Filled in by GCP, often the Compute Engine Default SA due to Org Policy
  - --set-secrets=GEMINI_API_KEY=GEMINI_API_KEY:latest,TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,TELEGRAM_CHAT_ID=TELEGRAM_CHAT_ID:latest,CRYPTOCOMPARE_API_KEY=CRYPTOCOMPARE_API_KEY:latest # Map secrets to env vars
  # FIREBASE_PROJECT_ID was removed from secrets as it's better handled via GOOGLE_CLOUD_PROJECT env var.
  - --project=telegram-signals-205cc
```

*   `--gen2`: Essential for using newer features and underlying Cloud Run infrastructure.
*   `--runtime`: Must match the Python version used locally (Python 3.11 was chosen after issues with 3.12 and `ta-lib`).
*   `--region`: Deployment location for the function.
*   `--source`: Specifies the directory containing the `main.py` and `requirements.txt`. This affects import paths.
*   `--entry-point`: The specific Python function within `main.py` to be executed.
*   `--trigger-http --allow-unauthenticated`: Configures the function to be invokable via HTTP without OIDC. If stricter security is needed, use `--no-allow-unauthenticated` and configure Cloud Scheduler with OIDC.
*   `--service-account`: Specifies the identity the function runs *as* at runtime. Due to an Organization Policy (`cloudbuild.useComputeServiceAccount`), this was often forced to be the Compute Engine Default Service Account.
*   `--set-secrets`: Mounts Secret Manager secrets as environment variables.
*   **`FIREBASE_PROJECT_ID` Handling**: Initially attempted to pass via `--set-secrets`. This caused "Invalid secret name" errors. Resolved by removing it from `cloudbuild.yaml` secrets and updating `functions/config.py` to use `os.getenv("GOOGLE_CLOUD_PROJECT")`, which is automatically available in the Cloud Function environment.

## 5. IAM Permissions (Critical & Complex)

This was the most complex part due to an Organization Policy (`constraints/cloudbuild.useComputeServiceAccount`) forcing builds to use the project's Compute Engine default service account (`[PROJECT_NUMBER]-compute@developer.gserviceaccount.com`).

*   **Compute Engine Default Service Account (Forced for Build & Runtime):**
    *   **Build-Time Roles Needed:**
        *   `roles/cloudfunctions.developer`: To deploy functions.
        *   `roles/iam.serviceAccountUser`: To act as itself (or other SAs if the build needed to impersonate, though not the primary issue here).
        *   `roles/artifactregistry.writer`: To push the built container image to Artifact Registry.
        *   Initially missed roles like `Logs Writer`, `Storage Object Viewer`, `Artifact Registry Reader`, leading to build failures. Adding these resolved Cloud Build permission errors.
    *   **Run-Time Roles Needed (for the same Compute Engine Default SA):**
        *   `roles/secretmanager.secretAccessor`: To access secrets specified in `--set-secrets` at runtime.
        *   `roles/datastore.user`: To read/write to Firestore.
        *   `roles/logging.logWriter`: To write application logs.
        *   `roles/run.invoker`: Required for Cloud Scheduler (or other services) to trigger the function via HTTP.

**Troubleshooting IAM:**
*   Error messages like `Secret Manager Secret Accessor` or `iam.serviceaccounts.actAs` during Cloud Build pointed to missing permissions for the SA executing the build (the Compute Engine Default SA in this case).
*   Use `gcloud projects get-iam-policy [PROJECT_ID]` and filter by member to verify roles.
*   Check Cloud Build logs and Cloud Function/Cloud Run logs for permission errors.

## 6. Code Adjustments for Cloud Functions

*   **Relative Imports:** All imports *within* the `functions` module must be relative (e.g., `from . import config`).
*   **Firebase Initialization:** `firebase_admin.initialize_app()` called globally in `main.py` with a check `if not firebase_admin._apps:` to ensure it runs once per instance.
*   **Configuration Loading:** `functions/config.py` uses `os.getenv()` to load secrets and configurations, which are made available via `--set-secrets` in `cloudbuild.yaml` or are standard GCP environment variables.

## 7. Dependency Management (`functions/requirements.txt`)

*   **`ta-lib` Saga:**
    *   Initial attempts with `TA-Lib` failed during Cloud Build due to missing C dependencies.
    *   Switched to `TA-Lib-Precompiled==0.4.25`. This worked but introduced `numpy` version sensitivity (required `numpy==1.26.4`).
    *   Ultimately, `TA-Lib` and `TA-Lib-Precompiled` were replaced with **`pandas-ta`** to simplify dependencies and resolve build/runtime issues, especially on macOS arm64 for local dev and for smoother cloud builds. `technical_analysis.py` was refactored to use `pandas-ta`.
*   **Python Version:** Started with Python 3.12, but `TA-Lib-Precompiled` (and other potential incompatibilities) led to a switch to Python 3.11, which was more stable with the chosen dependencies.
*   **`python-telegram-bot`:** Was initially missing from `requirements.txt`, causing `ModuleNotFoundError` at runtime. Adding `python-telegram-bot==20.3` (or a compatible version) resolved this.
*   **`pandas`:** A `ModuleNotFoundError: No module named 'pandas'` occurred despite it being in `requirements.txt`. This was mysteriously resolved by a forced rebuild/redeployment, suggesting a potential caching or build artifact issue that a clean build fixed. Ensure `pandas>=1.0.0` (or a specific working version) is present.

## 8. Firestore Database

*   Ensure a Firestore database is created in Native mode in a compatible region (e.g., `us-central1` or `nam5` if the function is in `us-central1`).
*   The function's runtime service account needs `roles/datastore.user`.
*   **Local Firestore Emulation/Connection:** For local development (`functions-framework`), `GOOGLE_APPLICATION_CREDENTIALS` environment variable must point to a valid service account JSON key file.
    *   Encountered `google.auth.exceptions.RefreshError: ('invalid_grant: Invalid JWT Signature.')` locally. This was resolved by regenerating the `firebase-adminsdk-fbsvc@...` service account key from GCP IAM & Admin -> Service Accounts, downloading the new JSON, and updating the local `service-account.json` file referenced by `GOOGLE_APPLICATION_CREDENTIALS`.

## 9. Cloud Scheduler Job Creation

*   Use `gcloud scheduler jobs create http ...`
*   `--schedule`: Cron expression (e.g., `"*/5 * * * *"`).
*   `--uri`: The HTTP trigger URL of the deployed function.
*   `--http-method=POST`.
*   If using `--no-allow-unauthenticated` on the function, set `--oidc-service-account-email` to the function's runtime service account. If using `--allow-unauthenticated`, OIDC is not strictly needed for invocation but consider security implications.

## 10. Runtime Errors & Debugging in Cloud

*   **`AttributeError: module 'main.config' has no attribute 'TRACKED_SYMBOLS'` / `KLINE_INTERVAL`**: Caused by changes in `config.py` (e.g., renaming `TRACKED_COINS` to `TRACKED_SYMBOLS`) not being present in the deployed version. Resolved by ensuring the correct code was deployed.
*   **`NameError: name 'confidence_score' is not defined`**: A Python runtime error in `main.py` due to a variable being used before assignment in a specific code path (e.g., forced signal block). Fixed by ensuring `confidence_score` was defined.
*   **`TypeError: save_position() takes 2 positional arguments but 6 were given`**: Error in `main.py` when calling `position_manager.save_position`. Fixed by changing `main.py` to pass a single dictionary argument to `save_position`.
*   **Telegram Issues (No Messages Received in Cloud despite Local Success):**
    *   Verified bot token and chat ID were correct in Secret Manager.
    *   Added `python-telegram-bot` to `requirements.txt`.
    *   The crucial fix was often related to other runtime errors (like the `TypeError` above) crashing the function before Telegram calls could be made or logged. Once these were fixed, and the correct token was deployed, messages started working.
    *   "Unknown Signal" formatting in Telegram was due to `telegram_bot.py` expecting "LONG"/"SHORT" but receiving "BUY". Fixed by mapping in `_format_signal_message`.
*   **Firestore Data Discrepancies (`initial_stop_loss` null):** Caused by `position_manager.save_position` expecting "LONG"/"SHORT" for SL/TP logic but receiving "BUY". Fixed by mapping in `save_position`.

## 11. Local Development & Testing (`functions-framework`)

*   Use `functions-framework --target=run_signal_generation --source=functions/main.py --debug --port=8080`.
*   Set `GOOGLE_APPLICATION_CREDENTIALS` to point to your service account key file.
*   Use a `.env` file for API keys and other configurations, loaded by `python-dotenv` in `config.py`.
*   Local `curl http://localhost:8080` can be used to trigger the function.
*   Kill old `functions-framework` processes if port conflicts occur (`lsof -i :8080`, `kill -9 [PID]`).

## 12. Verification

*   Monitor Cloud Build history.
*   Check Cloud Functions/Cloud Run console for healthy service (green checkmark, new revision active).
*   Thoroughly check Cloud Logging for the function for successful execution logs and absence of errors after deployment.
*   Verify expected side effects (Telegram messages, Firestore data).

This updated guide should provide a more accurate picture of the deployment process and common pitfalls. 