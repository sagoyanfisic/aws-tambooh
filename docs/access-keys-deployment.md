# Development deployment with IAM access keys

This is the development alternative requested for account **786638967830**, region **us-east-2**, because AWS Projects rejected `iam:CreateOpenIDConnectProvider` with an explicit service control policy (SCP) deny. Project administrators cannot override AWS-managed SCPs. The published restricted-actions list includes `iam:*Provider*`, but does not list `iam:CreateUser` or `iam:CreateAccessKey` in that statement. This does **not** prove that all other policies in the actual account allow those operations or application deployment.

References: [AWS Projects managed policies](https://docs.aws.amazon.com/accounts/latest/reference/scps-and-rcps-for-projects.html), [IAM access-key management](https://docs.aws.amazon.com/IAM/latest/UserGuide/access-key-self-managed.html).

The dev workflows now use an IAM user's access key stored in GitHub environment secrets. Production retains its separate OIDC configuration. Static credentials do not bypass SCPs. No account upgrade, AWS resource creation, credential creation, or deployment was performed while preparing these files.

## 1. Create access permissions in the target console

1. Open CloudFormation in account **786638967830**, region **us-east-2**. This procedure does not use or alter any local AWS profile.
2. Create a **new** stack named `tambooh-dev-key-access`, uploading [console-access-keys.json](../infrastructure/bootstrap/console-access-keys.json). JSON is a supported CloudFormation template format. Do not update the failed OIDC stack with this template.
3. Keep `Environment=dev`, `AccessRolePrefix=tambooh-dev-keys`, and `ExistingArtifactBucketName=tambooh-dev-artifacts-786638967830` for the bucket already created. An empty bucket parameter creates a private, encrypted, versioned bucket instead. Existing buckets are reused without modification.
4. Acknowledge `CAPABILITY_NAMED_IAM`, then create the stack. It creates a programmatic IAM user and a separate CloudFormation service role. No OIDC provider, console login profile, access key, or secret output is created by this template.
5. After `CREATE_COMPLETE`, record the outputs. With the default prefix, the user is `tambooh-dev-keys-github-deploy` and the execution role is `arn:aws:iam::786638967830:role/tambooh-dev-keys-cloudformation`.

The user's inline policy is limited to artifact access, application-stack CloudFormation operations, and passing the execution role to CloudFormation. It cannot create its own keys or administer IAM users. The execution role separately manages the application resources; some resource creation/list operations require account-level resource patterns. Neither identity receives `AdministratorAccess`. Conditions prevent IAM/S3 resources from being created in another account or region.

If IAM user creation, role creation, key creation, or another operation is denied by an SCP, stop and record the exact denied action. An additional Allow or a different credential cannot override it. Review AWS Projects' supported options or [advanced features](https://docs.aws.amazon.com/accounts/latest/reference/activate-advanced-features.html), including billing implications, before making any account changes. Activation is not performed by these files.

## 2. Create the key manually

In the **target account's IAM console**, open **Users → tambooh-dev-keys-github-deploy → Security credentials → Access keys → Create access key**. Choose the appropriate external application use case. Save the access key ID and secret access key in a password manager; the secret is shown only once. The administrator performing this step needs permission to create keys for this specific user.

Use the dedicated deployment user, never another account's keys. Do not paste either credential into chat, Git, workflow YAML, screenshots, or GitHub variables. The template deliberately does not use `AWS::IAM::AccessKey`, so key values cannot appear in stack outputs.

## 3. Configure the GitHub dev environment

Open **sagoyanfisic/aws-tambooh → Settings → Environments → dev**.

Add **Environment secrets**:

| Secret | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | Access key ID from the dedicated IAM user |
| `AWS_SECRET_ACCESS_KEY` | Its matching secret access key |

Set **Environment variables** from the successful stack outputs:

| Variable | Default value |
|---|---|
| `AWS_REGION` | `us-east-2` |
| `AWS_ARTIFACTS_BUCKET` | `tambooh-dev-artifacts-786638967830` |
| `AWS_CLOUDFORMATION_ROLE_ARN` | `arn:aws:iam::786638967830:role/tambooh-dev-keys-cloudformation` |

**Replace the existing execution-role variable**: the previous OIDC bootstrap failed, so its role must not be assumed to exist. `AWS_DEPLOY_ROLE_ARN` is not used by dev key authentication and can be removed from the dev environment. The production environment still needs its own deployment role.

Restrict the dev environment to the `dev` branch. Do not use a production environment's variables or secrets. Keep the workflows on the default branch so GitHub exposes the manual run button; select branch `dev` when starting the run.

## 4. Start a manual deployment

After reviewing and pushing the changed files yourself, open **Actions → Deploy dev → Run workflow → Branch: dev**. Alternatively run **Deploy TamBooh** with input **environment: dev**.

The workflow runs tests, loads the two GitHub secrets using `aws-actions/configure-aws-credentials`, checks STS account identity and the execution-role account/region, and only then validates/builds/deploys SAM. Authentication must be configured explicitly; the target check refuses local execution. No OIDC token is requested for dev authentication. The general workflow retains `id-token: write` for its separate production path, which still uses OIDC.

The verification is read-only. A successful STS check proves the selected account, not that the full deployment will be permitted. IAM/SCP restrictions can still prevent later resource creation. No workflow is triggered by a push.

## Troubleshooting

### API stage tagging failure and initial rollback

If `ApiStage` fails with `apigateway:TagResource` and `tambooh-dev` reaches `ROLLBACK_COMPLETE`, follow [the retained-data recovery runbook](recover-failed-deployment.md). Update this access stack with the corrected template first. Do not repeatedly rerun SAM or delete the retained DynamoDB table/S3 bucket. The runbook imports both existing data resources before resuming the full deployment.

### Missing SAM transform permission

If the change set fails with `cloudformation:CreateChangeSet` denied on `arn:aws:cloudformation:us-east-2:aws:transform/Serverless-2016-10-31`, update the **existing** `tambooh-dev-key-access` stack using the corrected `console-access-keys.json`. Keep its current parameters, acknowledge named IAM resources, and verify that the change set modifies the inline policies without replacing the IAM user or execution role. After `UPDATE_COMPLETE`, start a new dev deployment. Do not create a second stack with the same resource names or recreate access keys.

The bootstrap grants only `CreateChangeSet` on the AWS-owned SAM transform to both the execution role and deployment identity. The ARN contains `aws` instead of the application account ID. This is separate from the existing permissions on the application's stack and change sets. See [AWS's transform permission example](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/control-access-with-iam.html).

For an immediate manual repair in the target console, add [this narrowly scoped inline policy](../infrastructure/roles/cloudformation-sam-transform-policy.json) to `tambooh-dev-keys-cloudformation`. It supplements existing permissions; it must not replace the full `ApplicationResources` policy. Update the bootstrap stack afterward to keep its managed policy aligned. No AWS permissions are modified by editing the repository alone.

## Rotation and cleanup

Create a second access key for this same user, update both GitHub secrets, and run a new dev deployment. After confirming success, deactivate the old key, verify it is no longer used, and delete it. Delete unused keys when the demo ends. Do not delete this IAM user or stack while its keys remain in use. IAM users with active keys can require key deletion before CloudFormation can delete the user.

The keys grant deployment access until revoked. GitHub environment restrictions, review of workflow changes, and key rotation are required operational controls. OIDC remains the preferred alternative once this account permits it.

Anthropic uses its **own** API key in AWS Secrets Manager, unchanged. AWS access keys are not Anthropic keys, and neither belongs in the frontend.
