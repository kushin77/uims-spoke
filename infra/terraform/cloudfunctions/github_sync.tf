# Placeholder Terraform for Cloud Function github_sync
# Replace placeholders with real service account, runtime, and source upload

resource "google_cloudfunctions_function" "github_sync" {
  name        = "github-sync"
  runtime     = "python311"
  entry_point = "webhook"
  # source_archive_bucket = google_storage_bucket.functions_bucket.name
  # source_archive_object = "github_sync.zip"
  trigger_http        = true
  available_memory_mb = 256
  # Set env vars such as GITHUB_SECRET via google_cloudfunctions_function_iam_member or other resources
}
