# Recover the initial dev deployment without deleting retained data

Target: account **786638967830**, region **us-east-2**. No local default AWS profile is used. All steps below are operator actions in the target console; editing this repository does not perform them.

The reported first creation failed at `ApiStage` because the CloudFormation role lacked `apigateway:TagResource`. Other `Resource creation cancelled` events are consequences of rollback. The stack then reached `ROLLBACK_COMPLETE`. Its events explicitly show `DELETE_SKIPPED` for `PricesTable` and `RawDataBucket`; these resources were retained.

AWS permits only deletion of a stack in `ROLLBACK_COMPLETE`. Retrying SAM alone cannot update it. Creating a replacement stack without importing the retained table would collide with `tambooh-dev-prices`. Deleting that table would unnecessarily discard data. This procedure imports both retained resources instead.

References: [stack statuses](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/view-stack-events.html), [resource import](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/import-resources-manually.html).

## 1. Correct access permissions

Update the existing **`tambooh-dev-key-access`** stack with the revised `infrastructure/bootstrap/console-access-keys.json`. Preserve its parameters and resource names. Review the change set: its CloudFormation execution-role policy now includes explicit `apigateway:TagResource` and `apigateway:UntagResource` permissions on the same API Gateway resource scope already managed by that role. It also retains the earlier SAM transform permission.

Wait for `UPDATE_COMPLETE`. Do not recreate the IAM user, rotate credentials, or change role ARNs for this correction. A narrowly scoped manual supplemental policy is also provided in `infrastructure/roles/cloudformation-apigateway-tags-policy.json`, but updating the bootstrap is preferred so the stack's managed permissions stay aligned.

## 2. Record retained resource identities before removing the failed stack

In CloudFormation, open **`tambooh-dev` → Resources**. Record the **Physical ID** of:

| Logical ID | Expected physical identity |
|---|---|
| `PricesTable` | `tambooh-dev-prices` |
| `RawDataBucket` | The actual generated `tambooh-dev-rawdatabucket-...` name |

Verify those same resources exist in DynamoDB and S3 in the target account. Record their contents/item counts and actual configuration; preserve any data. The import template reflects the repository's initial table/bucket configuration, not an inspection of AWS. If they were modified manually, reconcile the import template with their real properties first.

Only after recording and verifying the retained identities, delete **the failed `tambooh-dev` CloudFormation stack** in `ROLLBACK_COMPLETE`. Do not delete the DynamoDB table or either S3 bucket. Do not delete the access stack. The log shows the data resources were already skipped during rollback; confirm they remain after stack deletion. This is an operator action, never automated by the workflow.

If the stack has any status other than `ROLLBACK_COMPLETE`, stop and inspect it instead of following this deletion step.

## 3. Import the existing data resources

Use **CloudFormation → Create stack → With existing resources (import resources)**. Upload `infrastructure/recovery/import-retained-data.json`. This is a native CloudFormation data-only template: it has no Lambda code, API, schedule, SAM transform, or new application resources.

Use stack name **`tambooh-dev`**, `Environment=dev`, and `RawDataBucketName` equal to the recorded physical bucket name. The template is guarded to the target account and region and requires an actual retained bucket name.

For the import mappings, select the existing physical resources:

| Logical ID | Identifier property | Value |
|---|---|---|
| `PricesTable` | `TableName` | `tambooh-dev-prices` |
| `RawDataBucket` | `BucketName` | The recorded retained bucket name |

If a service role is requested, use `arn:aws:iam::786638967830:role/tambooh-dev-keys-cloudformation`, or the actual output of your access stack if you customized its prefix. The operator must have permission to import these resources and pass that role. Do not choose an unrelated account's role.

Review the import change set: it must contain **Import** for those two resources only, with no additions, replacements or deletions. Execute it and wait for `IMPORT_COMPLETE`. Inspect imported resources and run drift detection before the next update. If the resources are still associated with another stack, stop and resolve ownership; do not delete them to force an import.

## 4. Resume the full SAM deployment

In GitHub **Settings → Environments → dev → Environment variables**, add:

```text
AWS_RAW_DATA_BUCKET_NAME = <recorded retained bucket name>
```

Push the repository changes yourself, including `template.yaml`, `scripts/deploy.sh`, and the workflow changes. The revised SAM template accepts `RawDataBucketName`; it preserves the imported bucket's explicit name instead of removing its `BucketName` property. Removing that property could request replacement. The deployment script passes the override when configured; when absent it lets SAM keep the existing stack parameter.

Start **Deploy dev** from the updated **dev** branch and **disable the Execute the change set checkbox** for this recovery run. The workflow prepares a SAM change set with `--no-execute-changeset` and does not execute application resource changes. A green review-only job is not a successful application deployment. Do not trigger an older workflow/template revision that lacks the retained-bucket parameter or review option.

In CloudFormation, inspect that prepared change set: the imported table and bucket must not be replaced or removed. Other resources are additions. If data resources would be replaced or removed, do not execute it; correct the template/parameters first. Once reviewed, execute this exact change set through the target console, then wait for the application stack to reach `UPDATE_COMPLETE`. Later normal workflow runs can leave the execution checkbox enabled.

For an explicitly authorized terminal session, `SAM_EXECUTE_CHANGESET=false` selects the same review-only behavior in `scripts/deploy.sh`. Do not use local default credentials. Keep the imported stack parameters and bucket name.

No successful import, deployment, source download, or data publication is claimed by this runbook. They require actual AWS evidence.
