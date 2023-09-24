#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

cp src/routes/_toctree.yml build/_toctree.yml

# Copy redirects yml file if exists
if [ -e src/routes/_redirects.yml ]
 then cp src/routes/_redirects.yml build/_redirects.yml
fi

# make `rel="stylesheet"` -> `rel="modulepreload"`
cd build
find . -name '*.html' -exec perl -pi -e 's/rel="stylesheet"/rel="modulepreload"/g' {} +
cd ..