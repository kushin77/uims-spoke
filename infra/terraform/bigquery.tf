/*
  BigQuery dataset and table stubs for analytics.
*/

# Variables defined in variables.tf

resource "google_project_service" "bigquery_api" {
  project = var.project
  service = "bigquery.googleapis.com"
}

resource "google_bigquery_dataset" "uims" {
  dataset_id = var.dataset
  project    = var.project
  location   = "US"
}

# Tables (examples): issues, events, sessions
# resource "google_bigquery_table" "issues" {
#   dataset_id = google_bigquery_dataset.uims.dataset_id
#   table_id   = "issues"
#   project    = var.project
#   schema     = file("./schemas/issues.json")
# }
