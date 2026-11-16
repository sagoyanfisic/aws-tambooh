# Frontend: published wholesale prices

The React/TypeScript/Vite frontend reads `GET /api/v1/prices`. It has no embedded agricultural prices, exchange rate, climate status, cost estimate, or AI key. Data is validated at the client boundary before rendering. The dashboard displays wholesale PEN prices, observation dates, market names, source institutions and links, missing values, quality flags, and an age warning for observations older than two days in America/Lima.

Search ignores accents and case; the market selector preserves separation between markets. A failed refresh keeps the last successful in-memory response and its original dates. Failed initial loads, no published data and empty filtered results have explicit states. Requests have cancellation and a 12-second timeout. Prices are fetched on load and explicit refresh, not by polling.

The household fields retain the illustrative four-person / USD 65 demonstration. They stay in browser memory and do not generate a plan, shopping list, currency conversion or unsupported financial total. Nutrition, meal planning, scenarios and Claude are not claimed as completed frontend features.

## Local development

Use Node.js 22 (Vite also supports Node 20.19+):

```bash
cd frontend
cp .env.example .env
npm ci
npm run dev
```

The example points to the operator's deployed dev API. For SAM local, set `VITE_API_BASE_URL=http://localhost:3000` in the private `.env`. Use `http://localhost:5173` for Vite so its origin matches the dev CORS allow-list.

`VITE_API_BASE_URL` is a public base URL including the `/dev` or `/prod` stage, without `/api/v1`. Vite embeds public `VITE_*` values during build. Never place AWS credentials, Anthropic keys, session tokens or household identifiers in those variables. [Vite environment documentation](https://vite.dev/guide/env-and-mode).

Dependencies are versioned and the lockfile is committed for `npm ci`. Tailwind uses its standard PostCSS integration; the former floating `latest` dependencies were replaced with pinned versions. [Tailwind/Vite integration](https://v3.tailwindcss.com/docs/guides/vite).

## Tests and build

```bash
cd frontend
npm run lint
npm test
npm run build
```

The frontend tests use Node's built-in runner and compiled TypeScript services. They mock fetch and check the deployed API response contract, date validation, missing values, PEN/kg vs PEN/liter labeling, filtering, API Gateway stage preservation, unsafe links and service failures. They require neither AWS nor Anthropic credentials.

CI also checks browser runtime dependencies with `npm audit --omit=dev --audit-level=high`. This requires registry access; an offline test/build does not establish vulnerability-audit results. Local browser preview was blocked by the execution environment (localhost binding denied and headless Chrome could not start), so desktop/mobile visual review and real browser CORS verification remain operator checks after deployment.

## Deployment through GitHub Actions

1. Update the **existing** `tambooh-dev-key-access` stack with `infrastructure/bootstrap/console-access-keys.json`. Keep its parameters and wait for `UPDATE_COMPLETE`. The deployment user gains only `ListBucket` / `GetBucketLocation` and `PutObject` under the environment-specific `tambooh-dev-frontendbucket-*` namespace. No raw-data write, object deletion, public ACL or new secret is granted. Keys and role names are unchanged.
2. Push the reviewed repository changes yourself. Start **Deploy dev** from branch **dev**, leaving **Execute the change set** enabled. Production uses its separate protected environment and still requires independent authorization/configuration.
3. SAM updates the existing stack, including the frontend bucket's public-access blocking, CORS and cache configuration. CORS allows only `https://<FrontendDistributionDomain>` plus `http://localhost:5173` for dev. These references do not create a cycle: the distribution depends only on its S3 origin, not the API.
4. The job sets up Node 22 and runs `python scripts/deploy_frontend.py dev`. This helper refuses local default profiles, checks STS account **786638967830**, reads only that application's stack outputs, and validates the destination names and stage before uploading.
5. The helper runs `npm ci`, lint, tests and the production build with `VITE_API_BASE_URL` from `ApiUrl`. Nothing needs to be copied from the API URL into GitHub variables manually.
6. Hashed assets are uploaded first under `assets/`, then `index.html` is uploaded last. Assets are immutable and cached for one year; HTML uses `no-cache,no-store,must-revalidate`. CloudFront minimum/default TTL are zero, with a maximum that permits asset caching. Previous hashed assets remain for open browser tabs; no `--delete` is used.
7. The helper verifies that the public CloudFront root serves the exact new HTML. It retries briefly for propagation and fails the job if this check fails. A successful HTML smoke check does not prove that a browser's API fetch/CORS works; open the deployed site and verify the expected products, dates and markets.

Review-only SAM runs skip frontend publication. No runtime public S3 bucket or website endpoint is enabled. CloudFront OAC remains the only public delivery path. Hashed filenames plus uncached HTML remove the need for routine global cache invalidations with this configuration; any older deployment with different cache headers may require an operator invalidation. [CloudFront versioning and invalidation](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Invalidation.html).

After the operator's confirmed dev deployment, the current site address is `https://dtwbd6mirzqkq.cloudfront.net`. Preparing these frontend changes does not publish new assets or claim that the new interface has been verified there.
