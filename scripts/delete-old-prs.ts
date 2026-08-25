#!/usr/bin/env -S deno run --allow-env --allow-net --allow-run --allow-read
// To format: npx prettier --write .
//
// Cleans up old PR documentation from the HF bucket.
// Lists all pr_* directories across all packages and deletes those older than 30 days.

const BUCKET_ID = "hf-doc-build/doc-dev";
const MAX_AGE_DAYS = 30;

const oneMonthAgo = new Date(Date.now() - MAX_AGE_DAYS * 24 * 3600 * 1000);
const token = Deno.env.get("HF_ACCESS_TOKEN")!;
const headers = { Authorization: `Bearer ${token}` };

interface BucketEntry {
	path: string;
	type: string;
	uploadedAt?: string;
}

/**
 * Non-recursive listing of one level of the bucket tree, following the
 * Link header for pagination.
 * https://huggingface.co/api/buckets/{namespace}/{name}/tree/{path}?recursive=false
 */
async function listDir(path = ""): Promise<BucketEntry[]> {
	const entries: BucketEntry[] = [];
	let url: string | undefined = `https://huggingface.co/api/buckets/${BUCKET_ID}/tree${
		path ? `/${path}` : ""
	}?recursive=false&limit=1000`;
	while (url) {
		const res = await fetch(url, { headers });
		if (!res.ok) {
			throw new Error(`Failed to list ${url}: HTTP ${res.status} ${(await res.text()).slice(0, 500)}`);
		}
		const batch = await res.json();
		if (!Array.isArray(batch)) {
			throw new Error(`Unexpected response listing ${url}: ${JSON.stringify(batch).slice(0, 500)}`);
		}
		entries.push(...batch);
		url = res.headers.get("link")?.match(/<([^>]+)>;\s*rel="next"/)?.[1];
	}
	return entries;
}

let totalDeleted = 0;
let totalKept = 0;
let failures = 0;

// Step 1: List all top-level packages in the bucket
for (const pkg of await listDir()) {
	if (pkg.type !== "directory") continue;

	// Step 2: List pr_* directories inside each package
	for (const entry of await listDir(pkg.path)) {
		if (entry.type !== "directory" || !entry.path.includes("/pr_")) continue;

		const uploadedAt = entry.uploadedAt ? new Date(entry.uploadedAt) : null;
		if (!uploadedAt) continue;

		if (uploadedAt < oneMonthAgo) {
			console.log(`Deleting ${entry.path} (uploaded ${uploadedAt.toISOString()})`);
			const proc = new Deno.Command("hf", {
				args: ["buckets", "rm", `${BUCKET_ID}/${entry.path}`, "--recursive", "-y"],
				env: { HF_TOKEN: token },
				stdout: "piped",
				stderr: "piped",
			});
			const output = await proc.output();
			if (!output.success) {
				console.error(`Failed to delete ${entry.path}:`, new TextDecoder().decode(output.stderr));
				failures++;
				continue;
			}
			totalDeleted++;
		} else {
			totalKept++;
		}
	}
}

console.log({ totalDeleted, totalKept, failures });

// Fail the job loudly when something went wrong, so breakage is visible
// instead of silently accumulating previews for months.
if (failures > 0) {
	Deno.exit(1);
}
