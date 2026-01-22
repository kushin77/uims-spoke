/*
  Pub/Sub topic placeholders for issue-events and dead-letter topics.
*/

# Variables defined in variables.tf

resource "google_project_service" "pubsub_api" {
  project = var.project
  service = "pubsub.googleapis.com"
}

resource "google_pubsub_topic" "issue_events" {
  name    = "issue-events"
  project = var.project
}

resource "google_pubsub_topic" "dead_letter" {
  name    = "issue-events-deadletter"
  project = var.project
}
