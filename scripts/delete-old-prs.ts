#!/usr/bin/env -S deno run --allow-env --allow-net --allow-run --allow-read
// To format: npx prettier --write .
import { commit, listFiles } from "npm:@huggingface/hub@0.15.1";

const oneMonthAgo = new Date(Date.now() - 30 * 24 * 3600 * 1000);

const allFiles = listFiles({
	repo: { type: "dataset", name: "hf-doc-build/doc-build-dev" },
	recursive: true,
	expand: true,
});

const filesToDelete: string[] = [];

let fileCount = 0;
let filesWithoutDates = 0;

for await (const file of allFiles) {
	fileCount++;
	
	if (file.type !== "file" || !file.path.endsWith(".zip")) {
		continue;
	}

	const date = file.lastCommit?.date;

	if (!date) {
		filesWithoutDates++;
		continue;
	}

	if (oneMonthAgo < new Date(date)) {
		continue;
	}

	filesToDelete.push(file.path);
}

console.log({fileCount, filesWithoutDates});

if (filesToDelete.length) {
	console.log("deleting", filesToDelete.length, "files");
	await commit({
		repo: { type: "dataset", name: "hf-doc-build/doc-build-dev" },
		credentials: { accessToken: Deno.env.get("HF_ACCESS_TOKEN") },
		title: "Delete old docs",
		operations: filesToDelete.map((file) => ({
			operation: "delete",
			path: file,
		})),
	});
}
