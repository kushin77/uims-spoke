/*
  Example remote backend configuration for Terraform using GCS.
  Update with your `bucket` and `prefix` before enabling in CI.
  Note: Do NOT commit production credentials. Use GitHub Secrets for CI.
*/

# Backend variables are defined in variables.tf
# Uncomment below when ready to configure remote state
#
# terraform {
#   backend "gcs" {
#     bucket = "my-tf-state-bucket"
#     prefix = "uims-spoke/terraform"
#   }
# }
