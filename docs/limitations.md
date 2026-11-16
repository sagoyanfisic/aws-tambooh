# Limitations

The application has not been AWS-deployed or production-verified. Sample prices are not current market prices. Climate scenarios are arithmetic simulations. CloudFront OAC exists in SAM; API CORS remains unrestricted and requires a deployment-specific allow-list. Other countries are outside the MVP.

Ingestion tests use text fixtures, extracted-table mocks and simulated official pages. All four live PDF layouts and us-east-1 reachability remain unverified. Unknown layouts fail publication. Historical trend calculations and verified recipe/product mappings remain incomplete; the API exposes insufficient_history or DATA_UNAVAILABLE rather than invented trends or incomplete zero-cost meals. Wholesale prices must never be relabeled retail.

Daily source processing is sequential to enforce shared-domain pacing. Publication is atomic per source via manifests, not a global transaction across all sources. Historical/staging versions have no automated cleanup. Raw S3 objects expire after 90 days; curated snapshots remain. Runtime dependencies require network access to build; the local SAM build attempt could not resolve the package registry.

