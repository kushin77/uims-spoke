# Terraform for uims-spoke

This folder contains Terraform stubs and example configuration to provision the data layer for the UIMS spoke.

Quickstart (local, for development):

1. Copy example variables and edit values:

```bash
cp terraform.tfvars.example terraform.tfvars
```

2. (Optional) Configure a local backend or leave backend variables empty to use local state for experiments.

3. Initialize and run a plan:

```bash
terraform init
terraform plan -var-file=terraform.tfvars
```

CI / Production notes:

- Configure a GCS bucket for remote state and set `backend_bucket` and `backend_prefix` in CI secrets.
- Provide a service account with least-privilege for Terraform (project editor is too broad; grant specific roles required).
- Enable APIs via `google_project_service` resources in the stubs.

Security:

- Never commit `terraform.tfvars` with secrets.
- Use Secret Manager or GitHub Secrets for CI credentials.
