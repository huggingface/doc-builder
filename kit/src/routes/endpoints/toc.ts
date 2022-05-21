import path from "path";
import fs from "fs";
import yaml from "js-yaml";

export interface RawChapter {
  title: string;
  local?: string;
  new?: boolean;
  local_fw?: { pt: string; tf: string; };
  quiz?: string;
  sections?: RawChapter[];
}

const flattener = (_flatChapters: RawChapter[], chapter: RawChapter): RawChapter[] => {
  const sections = chapter?.sections as RawChapter[];
  _flatChapters.push(chapter);
  if (sections) {
    for (const section of sections) {
      flattener(_flatChapters, section);
    }
  }
  return _flatChapters;
};

export async function get() {
  const filepath = path.join(import.meta.url.replace('file://', ''), '../..', '_toctree.yml');
  const content = (await fs.promises.readFile(filepath)).toString("utf-8");

  const chapters: RawChapter[] = yaml.load(content) as RawChapter[];
  const chaptersFlat: RawChapter[] = chapters.reduce(flattener, []);

  return {
    body: chaptersFlat
  }
}
