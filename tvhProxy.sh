#!/bin/bash
if [ -f .env ] ; then 
    source .env
fi

# https://stackoverflow.com/questions/59895/how-to-get-the-source-directory-of-a-bash-script-from-within-the-script-itself
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd $DIR 

source .venv/bin/activate
python tvhProxy.py
