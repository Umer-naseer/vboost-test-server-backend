#!/usr/bin/env bash
set -e

if [ "vboost" != "$(whoami)" ]; then
    echo "Must be run under vboost, current user: $USERNAME."
    exit 1
fi

. ../venv/vboost/bin/activate

# Fix permissions
if [ -n "${JENKINS_HOME}" ]; then
    sudo chown -R vboost:vboost .
fi

# If NOT run under Jenkins, update the code
if [ -z "${JENKINS_HOME}" ]; then
    hg pull
    hg update
fi

# Prepare requirements
pip -q install -r requirements.txt
pip uninstall -y -r requirements_uninstall.txt
pip install -I -r requirements2.txt

# If we are under Jenkins, run the testing scripts
if [ -n "${JENKINS_HOME}" ]; then
    python manage.py jenkins --enable-coverage
fi

# Deploy
python manage.py migrate --noinput
python manage.py collectstatic --noinput

sudo supervisorctl restart vboost:*
