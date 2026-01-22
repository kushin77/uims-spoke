terraform {
  required_version = ">= 1.2"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# BigQuery dataset and tables will be defined here.
# Firestore, Memorystore, Pub/Sub resources will be added as modules.

// Example placeholder resource
// resource "google_bigquery_dataset" "uims_analytics" {
//   dataset_id = "uims_analytics"
//   location   = var.region
// }
