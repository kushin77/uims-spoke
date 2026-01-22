/*
  Memorystore (Redis) placeholder for uims-spoke.
*/

# Variables defined in variables.tf

resource "google_project_service" "redis_api" {
  project = var.project
  service = "redis.googleapis.com"
}

# Example stub for memorystore_instance (uncomment and configure when ready)
# resource "google_redis_instance" "uims_redis" {
#   name           = "uims-redis"
#   tier           = "STANDARD_HA"
#   memory_size_gb = 1
#   region         = var.region
#   project        = var.project
# }
