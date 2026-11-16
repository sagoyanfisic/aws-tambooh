# Configure access in the TamBooh account

Target account: **786638967830**. Region: **us-east-2**. The operator's local default AWS profile must not be used.

The account-guarded bootstrap creates or updates only the two dedicated IAM roles and the GitHub OIDC provider. It does not deploy Lambda, modify an existing artifact bucket or create permanent access keys. Previewing a plan does not contact AWS.

## Preferred: paste a CloudFormation template in the console

Use the complete standalone template `infrastructure/bootstrap/console.yaml`. It creates new access roles with prefix `tambooh-dev-bootstrap`, so roles previously created manually are not overwritten. There is no CLI/profile requirement for this option.

1. Sign into account **786638967830**, select **us-east-2**, and open CloudFormation. Create stack with new resources and use the template editor, or upload the YAML file.
2. Use stack name `tambooh-dev-access`.
3. `GitHubOidcSubject`: paste the exact `sub` from the deployment's Inspect OIDC claims step (see below). No guessed subject or wildcard.
4. `ExistingArtifactBucketName`: keep `tambooh-dev-artifacts-786638967830` if it already exists; clear the parameter if CloudFormation should create it. Reused buckets are not modified; verify encryption/public blocking yourself.
5. `ExistingOidcProviderArn`: if the provider exists, enter `arn:aws:iam::786638967830:oidc-provider/token.actions.githubusercontent.com`. Otherwise leave empty. A reused provider must already have issuer `https://token.actions.githubusercontent.com` and audience `sts.amazonaws.com`; this stack does not edit external providers.
6. Keep `AccessRolePrefix=tambooh-dev-bootstrap`. If those new names also exist outside this stack, choose another unique `tambooh-dev-...` prefix. The application stack remains `tambooh-dev`.
7. Acknowledge creation of named IAM resources and create the stack. After `CREATE_COMPLETE`, copy its outputs to the GitHub `dev` environment:

| Stack output | GitHub environment variable |
|---|---|
| GitHubDeploymentRoleArn | AWS_DEPLOY_ROLE_ARN |
| CloudFormationExecutionRoleArn | AWS_CLOUDFORMATION_ROLE_ARN |
| ArtifactsBucketName | AWS_ARTIFACTS_BUCKET |
| DeploymentRegion | AWS_REGION |

These outputs override the workflows' old default role ARNs. Start a new Deploy dev run. For direct local SAM deploy, also override the old execution-role default with `AWS_CLOUDFORMATION_ROLE_ARN` when using scripts/deploy.sh, or pass `--role-arn` explicitly.

Resource conditions prevent this console template from creating roles/provider/bucket outside account 786638967830 and region us-east-2. On a wrong target, it does not produce the intended access outputs. This template has been linted offline; no stack creation is claimed.

The following CLI option is an alternative for updating the original dedicated role names, rather than creating the new console-managed roles.

## 1. Obtain the real GitHub subject

Push the updated development workflow, then start a new **Deploy dev** run from branch **dev**. The **Inspect OIDC claims** step runs before AWS login and prints only selected metadata: issuer, audience, subject, repository and ref. The raw JWT is masked and never printed. The subsequent AWS login may fail until bootstrap is complete.

Copy the complete `sub` from that step. Do not reconstruct it from an environment numeric ID. Current formats supported by the bootstrap are:

```text
repo:sagoyanfisic/aws-tambooh:environment:dev
repo:sagoyanfisic@OWNER_ID/aws-tambooh@REPOSITORY_ID:environment:dev
```

Use only the format actually emitted by this repository. An exact observed subject is required; no wildcards are accepted. A customized subject containing extra workflow-specific claims requires a separate reviewed policy; this bootstrap refuses it.

## 2. Preview the plan locally (no AWS access)

```bash
python3 scripts/bootstrap_access.py --subject 'PASTE_THE_EXACT_SUB_HERE'
```

The script loads `infrastructure/bootstrap/template.json`, resolves its role policies, and prints the planned trust and permissions. The CloudFormation template can describe a fresh bootstrap, but the CLI path below also handles dedicated roles already created manually, without deleting or importing them.

## 3. Apply through the target account's CloudShell

Sign into account **786638967830**, select Ohio, and open AWS CloudShell. Use an existing session with permission to create/update the two IAM roles, their inline policies, and the OIDC provider. No new human IAM user is required.

Clone the repository's updated branch inside CloudShell (or upload the script and template preserving their paths):

```bash
git clone --branch dev https://github.com/sagoyanfisic/aws-tambooh.git
cd aws-tambooh
python3 scripts/bootstrap_access.py \
  --cloudshell \
  --subject 'PASTE_THE_EXACT_SUB_HERE' \
  --apply
```

For a private repository, upload the files or use your approved GitHub authentication. Do not put GitHub or AWS tokens in command URLs.

`--cloudshell` is an explicit opt-in to the target console session, for use only inside that account's CloudShell. It refuses `AWS_PROFILE` overrides. The first AWS request checks STS caller identity. If the account differs from **786638967830**, the script stops before any IAM or S3 mutation.

Alternatively, from a local terminal, use an explicitly authorized AWS CLI profile:

```bash
python3 scripts/bootstrap_access.py \
  --profile YOUR_TAMBOOH_PROFILE \
  --subject 'PASTE_THE_EXACT_SUB_HERE' \
  --apply
```

Without `--profile` or `--cloudshell`, apply fails before contacting AWS. A profile literally named `default` is refused. Ambient access-key variables are removed from the child process when using an explicit profile, so they cannot shadow it. No AWS configuration file is rewritten.

## What apply changes

- Reuses `token.actions.githubusercontent.com`, or creates the provider when absent. Adds audience `sts.amazonaws.com` if missing; other audiences are preserved.
- Creates or updates the trust of `tambooh-dev-github-deploy` to the exact verified subject and provider in this account. Its inline policy permits artifact uploads, application CloudFormation deployment and passing only the execution role to CloudFormation.
- Creates or updates `tambooh-dev-cloudformation`, trusted by `cloudformation.amazonaws.com`. Its policy manages the application's required resources. IAM role management/pass-role is limited to SAM-generated runtime-role name patterns.
- Updates only inline policy names `DeployApplication` and `ApplicationResources`. Other attached/inline policies are left untouched and must be reviewed separately if these roles already existed. There is no automatic rollback of earlier successful IAM operations after a later permission failure; rerun after correcting the operator's permissions.

The bootstrap policy is application-scoped, not `AdministratorAccess`. Some API Gateway/CloudFront identifiers are generated at creation time; the template documents the necessary collection/account-level resource patterns. Permission boundaries and organization SCPs may impose additional restrictions; those are not changed by this script.

The bootstrap does **not** modify an existing artifact bucket. Verify that `tambooh-dev-artifacts-786638967830` exists in Ohio and has public access blocked, SSE-S3 encryption and versioning, as described in deployment.md. For a fresh CloudFormation bootstrap the template also defines that bucket; do not deploy that stack over already manually created names without an import/reuse plan.

## 4. Configure GitHub and verify

The script prints the four GitHub environment values after success. In **Settings → Environments → dev**, set those values and allow deployment from branch `dev`. No AWS access keys are stored in GitHub.

Start a new **Deploy dev** run. Passing OIDC confirms federation only; the next steps separately validate build and resource-creation permissions. Do not rerun an old commit when testing changed workflow files.

If `InvalidIdentityToken` remains, inspect the provider issuer and ClientIDList through this same verified account context. A subject mismatch usually requires reviewing role trust; do not loosen it to `repo:*`. Do not delete a shared provider or change the other account's default profile as a workaround.

## Local validation

Unit tests mock all AWS calls. They cover wrong-account refusal before IAM changes, default-profile refusal, exact legacy/immutable subjects, credential-environment isolation and updates restricted to the dedicated roles. The template is linted offline. Actual IAM/SCP behavior and deployment success remain unverified until the operator runs it in the new account.
