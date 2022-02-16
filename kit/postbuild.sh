#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

declare -a langs

langs=$(ls  build | egrep '^([a-z]{2})$')

for lang in ${langs}; do
  cp src/routes/${lang}/_toctree.yml build/${lang}/_toctree.yml
  mv build/${lang}.html build/${lang}/index.html
done
