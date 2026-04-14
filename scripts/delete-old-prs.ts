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

// Step 1: List all top-level packages in the bucket
const packagesRes = await fetch(
	`https://huggingface.co/api/repos/bucket/${BUCKET_ID}/tree?recursive=false`,
	{ headers },
);
const packages: { path: string; type: string }[] = await packagesRes.json();

let totalDeleted = 0;
let totalKept = 0;

for (const pkg of packages) {
	if (pkg.type !== "directory") continue;

	// Step 2: List pr_* directories inside each package
	const entriesRes = await fetch(
		`https://huggingface.co/api/repos/bucket/${BUCKET_ID}/tree?path_prefix=${pkg.path}/&recursive=false`,
		{ headers },
	);
	const entries: { path: string; type: string; uploadedAt?: string }[] = await entriesRes.json();

	for (const entry of entries) {
		if (entry.type !== "directory" || !entry.path.includes("/pr_")) continue;

		const uploadedAt = entry.uploadedAt ? new Date(entry.uploadedAt) : null;
		if (!uploadedAt) continue;

		if (uploadedAt < oneMonthAgo) {
			console.log(`Deleting ${entry.path} (uploaded ${uploadedAt.toISOString()})`);
			const proc = new Deno.Command("hf", {
				args: ["buckets", "rm", `hf-doc-build/doc-dev/${entry.path}`, "--recursive", "-y"],
				env: { HF_TOKEN: token },
				stdout: "piped",
				stderr: "piped",
			});
			const output = await proc.output();
			if (!output.success) {
				console.error(`Failed to delete ${entry.path}:`, new TextDecoder().decode(output.stderr));
			}
			totalDeleted++;
		} else {
			totalKept++;
		}
	}
}

console.log({ totalDeleted, totalKept });
