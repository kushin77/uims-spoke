variable "enabled" {
  type    = bool
  default = false
}

variable "memory_size_gb" {
  type    = number
  default = 1
}

variable "environment" {
  type    = string
  default = "dev"
}

resource "google_redis_instance" "uims_redis" {
  count          = var.enabled ? 1 : 0

  name           = "uims-redis"
  tier           = "STANDARD_HA"
  memory_size_gb = var.memory_size_gb
  region         = var.region
  project        = var.project

  redis_version = "REDIS_6_X"

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

output "redis_instance_name" {
  value       = length(google_redis_instance.uims_redis) > 0 ? google_redis_instance.uims_redis[0].name : null
  description = "The memorystore instance name (when enabled)"
}
