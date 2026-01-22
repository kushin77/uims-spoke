variable "project_id" {
  type        = string
  description = "GCP project id for UIMS resources"
}

variable "project" {
  type        = string
  description = "GCP project id (alias for project_id)"
  default     = ""
}

variable "region" {
  type        = string
  description = "GCP region"
  default     = "us-central1"
}

variable "dataset" {
  type        = string
  description = "BigQuery dataset name"
  default     = "uims_dataset"
}

variable "environment" {
  type        = string
  description = "Environment (dev, staging, prod)"
  default     = "dev"
}

variable "memory_size_gb" {
  type        = number
  description = "Redis memory size in GB"
  default     = 1
}

variable "redis_enabled" {
  type        = bool
  description = "Whether to provision Redis"
  default     = false
}

variable "backend_bucket" {
  type        = string
  description = "GCS bucket for Terraform backend"
  default     = ""
}

variable "backend_prefix" {
  type        = string
  description = "Prefix for Terraform state in backend bucket"
  default     = "uims-spoke"
}
