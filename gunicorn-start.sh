#!/bin/bash

NAME="vboost"                                   # Name of the application
DJANGODIR=/home/vboost/vbo            # Django project directory
SOCKFILE=/home/vboost/run/gunicorn.sock   # we will communicate using this unix socket
USER=root                                      # The user to run as
GROUP=webdata                                   # The group to run as
TIMEOUT=150
NUM_WORKERS=4                                   # How many worker processes should Gunicorn spawn
DJANGO_SETTINGS_MODULE=vboostoffice.settings          # Which settings file should Django use
DJANGO_WSGI_MODULE=vboostoffice.wsgi                  # WSGI module name

echo "Starting $NAME as `whoami`"

# Activate the virtual environment
cd $DJANGODIR
source /home/ubuntu/env/bin/activate
export DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE
export PYTHONPATH=$DJANGODIR:$PYTHONPATH

# Create the run directory if it doesn't exist
RUNDIR=$(dirname $SOCKFILE)
test -d $RUNDIR || mkdir -p $RUNDIR

# Start your Django Unicorn
exec gunicorn ${DJANGO_WSGI_MODULE}:application \
  --name $NAME \
  --workers $NUM_WORKERS \
  --user $USER \
  --bind=unix:$SOCKFILE \
  --timeout $TIMEOUT
