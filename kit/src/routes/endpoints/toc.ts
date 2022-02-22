import path from "path";
import fs from "fs";
import yaml from "js-yaml";

export async function get() {
  const filepath = path.join(import.meta.url.replace('file://', ''), '../..', '_toctree.yml');
  const content = (await fs.promises.readFile(filepath)).toString("utf-8");

  return {
    body: yaml.load(content)
  }
}