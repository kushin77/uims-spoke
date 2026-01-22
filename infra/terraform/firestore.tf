/*
  Firestore (Native) placeholder resources for uims-spoke.
  These are starter stubs — configure `project` and run with proper credentials.
*/

# Variables defined in variables.tf

# Enable Firestore API
resource "google_project_service" "firestore_api" {
  project = var.project
  service = "firestore.googleapis.com"
}

# NOTE: Firestore database in Native mode must be created via console or gcloud for some orgs.
# You can use google_firestore_database if supported in your provider version.
