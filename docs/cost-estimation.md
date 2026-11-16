# Cost assumptions

The MVP is designed for low idle cost: Lambda, API Gateway HTTP API, DynamoDB on-demand, S3, Step Functions, EventBridge, CloudWatch, and optional Claude API usage are variable. CloudFront and S3 incur delivery/storage charges. Claude usage is the largest variable risk; keep it disabled for the public demo unless a budget is approved. AWS Budgets can alert at thresholds such as 50%, 80%, and 100%, but cannot hard-stop spending.

