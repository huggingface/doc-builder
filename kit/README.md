# HTML generator for the docs

## Building the docs

- Install `nodejs` / `npm`
- Run `npm install`
- Copy the mdx docs into the routes folder
- set `DOCS_VERSION` in the env to the correct prefix (eg `master`)
- set `DOCS_LANGUAGE` in the env to the correct language (eg `en`)
- Run `npm run run build`

The generated html files and assets are in the `build` folder.

## Previewing the docs

Instead of `npm run build`, do `npm run dev`. Then go to http://localhost:3000/docs/transformers/master/en (or replace `master` with the correct prefix).
