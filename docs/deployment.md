# Deployment

1. Create the secret without putting its value in SAM or GitHub: `aws secretsmanager create-secret --name tambooh/dev/anthropic-api-key --secret-string '{"ANTHROPIC_API_KEY":"..."}'`.
2. Install Python 3.12, Node 22, AWS CLI, and SAM CLI.
3. Run `pip install -e '.[dev]'`, then `cd frontend && npm install`.
4. Run `sam validate --template-file template.yaml` and `sam build`.
5. Deploy with `sam deploy --guided` using `Environment=dev`, `EnableAI=false`, and the existing secret ID.
6. Build and upload the frontend to the `FrontendBucketName` output. Serve it through `FrontendDistributionDomain`.

Production uses a separate secret, GitHub environment, stack, and approval gate. The secret is rotated with `aws secretsmanager put-secret-value`; the Lambda cache refreshes on a new execution environment.

