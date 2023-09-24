import fs from "fs";
import path from "path";

const directoryPath = "./build"; //build dir

// Recursively read all HTML files in a directory
function readFiles(directory) {
    const files = fs.readdirSync(directory);

    files.forEach(file => {
        const filePath = path.join(directory, file);
        const stat = fs.statSync(filePath);

        if (stat.isDirectory()) {
            readFiles(filePath);
        } else if (filePath.endsWith('.html')) {
            processFile(filePath);
        }
    });
}

function processFile(filePath) {
    const content = fs.readFileSync(filePath, 'utf-8');

    const metas = Array.from(content.matchAll(/<meta[^>]*>/g)).map(m => m[0]);

    if (metas.length) {
        let newContent = content;

        // Remove all meta tags from their original locations
        for (const tag of metas) {
            newContent = newContent.replace(tag, '');
        }

        // Add them back at the start of the head
        newContent = newContent.replace('<!-- META HERE -->', '<!-- META HERE -->' + metas.join(''));

        fs.writeFileSync(filePath, newContent);
    }
}

readFiles(directoryPath);
