#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

cp src/routes/_toctree.yml build/_toctree.yml

# Copy redirects yml file if exists
if [ -e src/routes/_redirects.yml ]
 then cp src/routes/_redirects.yml build/_redirects.yml
fi

# To avoid conflict with Hub Tailwind CSS build, 
# 1. making doc-builder's PostCSS geenrated file an empty one
# 2. making `rel="stylesheet"` -> `rel="modulepreload"`
> $(find . -regex '.*build.*.css')
cd build
find . -name '*.html' -exec perl -pi -e 's/rel="stylesheet"/rel="modulepreload"/g' {} +
cd ..

# Replace hash in filenames of build artifacts with substring `hf-doc-builder`
# so that git diff can be smaller since different hashes create new files that dont share git history
# ex: assets/paths-4b3c6e7e.js -> assets/paths-hf-doc-builder.js
cd build
find . -type f -exec perl -pi -e 's/-[a-z0-9]{8}\.(js|css)/-hf-doc-builder\.$1/g' {} +
find . -name '*.js' -o -name '*.css' | perl -pe 'print $_; s/-[a-z0-9]{8}\.(js|css)/-hf-doc-builder\.$1/g' | xargs -n2 mv
cd ..
