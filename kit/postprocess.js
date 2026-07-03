import fs from "fs";
import path from "path";

const directoryPath = "./build"; //build dir

// Recursively read all HTML files in a directory
function readFiles(directory) {
	const files = fs.readdirSync(directory);

	files.forEach((file) => {
		const filePath = path.join(directory, file);
		const stat = fs.statSync(filePath);

		if (stat.isDirectory()) {
			readFiles(filePath);
		} else if (filePath.endsWith(".html")) {
			processFile(filePath);
		}
	});
}

// Regex to match `meta name="hf:doc:metadata"`, rendered from the page's
// `<svelte:head>` (see doc_builder/convert_md_to_mdx.py)
const REGEX_HF_METADATA = /<meta\s+name="hf:doc:metadata"[^>]*>/;

function processFile(filePath) {
	// Read the file synchronously
	const data = fs.readFileSync(filePath, "utf8");
	// Extract the matched group using the regex
	const match = data.match(REGEX_HF_METADATA);
	if (!match) {
		throw new Error(`hf:doc:metadata meta tag not found in ${filePath}`);
	}
	// Copy the meta tag to the first line: moon-landing slices the file at the
	// first newline — line 1 is parsed for hf:doc:metadata and everything after
	// it is served as the page component.
	const lines = data.split("\n");
	// SvelteKit 2 renders the first head elements on the same line as the
	// `<meta charset>` tag (app.html is a single line); move them to the next
	// line so they stay part of the page component.
	const CHARSET_TAG = '<meta charset="utf-8" />';
	const headStart = lines[0].startsWith(CHARSET_TAG) ? lines[0].slice(CHARSET_TAG.length) : "";
	if (headStart) {
		lines[0] = CHARSET_TAG + match[0];
		lines.splice(1, 0, "\t\t" + headStart);
	} else {
		lines[0] += match[0];
	}
	// Join the lines back and write to the file synchronously
	const updatedData = lines.join("\n");
	fs.writeFileSync(filePath, updatedData, "utf8");
}

readFiles(directoryPath);
