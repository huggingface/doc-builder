#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

cp src/routes/_toctree.yml build/_toctree.yml

# To avoid conflict with Hub Tailwind CSS build, 
# making doc-builder's PostCSS geenrated file an empty one
> $(find . -regex '.*build.*.css')
