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

// Regex to match `meta name="hf:doc:metadata"`
const REGEX_HF_METADATA = /<!-- HEAD_svelte-.+_START -->(.+)<!-- HEAD_svelte-.+_END -->/s;

function processFile(filePath) {
	// Read the file synchronously
	const data = fs.readFileSync(filePath, "utf8");
	// Extract the matched group using the regex
	const match = data.match(REGEX_HF_METADATA);
	// Append macthed group 1 to the first line
	const lines = data.split("\n");
	lines[0] += match[1];
	// Join the lines back and write to the file synchronously
	const updatedData = lines.join("\n");
	fs.writeFileSync(filePath, updatedData, "utf8");
}

readFiles(directoryPath);
