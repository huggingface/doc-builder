#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

cp src/routes/_toctree.yml build/_toctree.yml

# To avoid conflict with Hub Tailwind CSS build, 
# 1. making doc-builder's PostCSS geenrated file an empty one
# 2. making `rel="stylesheet"` -> `rel="modulepreload"`
> $(find . -regex '.*build.*.css')
cd build
find . -name '*.html' -exec sed -i '' 's/rel="stylesheet"/rel="modulepreload"/g' {} \;
