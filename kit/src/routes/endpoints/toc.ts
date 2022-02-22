import type { RequestEvent } from "@sveltejs/kit";
import path from "path";
import fs from "fs";
import yaml from "js-yaml";

export async function get(input: RequestEvent) {
  const lang = input.url.searchParams.get('lang') || 'en';
  const filepath = path.join(import.meta.url.replace('file://', ''), '../..', lang, '_toctree.yml');
  const content = (await fs.promises.readFile(filepath)).toString("utf-8");

  return {
    body: yaml.load(content)
  }
}