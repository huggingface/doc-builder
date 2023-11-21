import fs from "fs";
import path from "path";
import { runtime_directory } from "../node_modules/@sveltejs/kit/src/core/utils.js";

// Step 1: replace client.js
const sourceFilePathClient = path.resolve("./svelteKitCustomClient/client.js");
const destinationFilePathClient = path.join(runtime_directory, "client/client.js");
fs.copyFileSync(sourceFilePathClient, destinationFilePathClient);

// Step 2: export hf doc const env vars
const sourceFilePathConsts = path.join(runtime_directory, "client/hfDocConsts.js");
const constsString = `export const DOCS_LIBRARY = "${process.env.DOCS_LIBRARY}";
export const DOCS_VERSION = "${process.env.DOCS_VERSION}";
export const DOCS_LANGUAGE = "${process.env.DOCS_LANGUAGE}";`;
fs.writeFileSync(sourceFilePathConsts, constsString, "utf8");
