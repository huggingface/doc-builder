#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

cp src/routes/_toctree.yml build/_toctree.yml

# To avoid conflict with Hub Tailwind CSS build, 
# 1. making doc-builder's PostCSS geenrated file an empty one
# 2. making `rel="stylesheet"` -> `rel="modulepreload"`
> $(find . -regex '.*build.*.css')
cd build
find . -name '*.html' -exec perl -pi -e 's/rel="stylesheet"/rel="modulepreload"/g' {} +

# Remove hash from files
find . -name '*.html' -exec perl -pi -e 's/-[a-z0-9]{8}\.(js|css)/-hf-doc-builder\.$1/g' {} +
find . -name '*.js' -o -name '*.css' | perl -pe 'print $_; s/-[a-z0-9]{8}\.(js|css)/-hf-doc-builder\.$1/g' | xargs -n2 mv