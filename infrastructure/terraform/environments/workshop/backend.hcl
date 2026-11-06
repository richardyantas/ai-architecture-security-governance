# cp backend.hcl.example backend.hcl   (backend.hcl is NOT committed)
bucket       = "maintenance-ai-tfstate-499503229865"
key          = "workshop/terraform.tfstate"
region       = "us-east-1"
encrypt      = true
use_lockfile = true # S3-native locking (Terraform >= 1.10), no DynamoDB table needed
