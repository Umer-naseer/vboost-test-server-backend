# README #

This README is documenting how to install this project on a development machine. This instruction is a draft and subject to change.

### Prerequisites ###

First of all, you need:

- A Linux-based system, preferably Debian or Ubuntu
- MySQL (server, client, and development packages)
- Python 2.7.x
- python-pip
- python-virtualenv
- Mercurial


Also the suggestion is to use PyCharm Community Edition as IDE.

## STEP 1. ##
*Create a directory where you will put the project and go to it (the folder of your choice, in this example: "src").*

```bash
cd ~/ && mkdir src  && cd ~/src
```

## STEP 2.
*Install the required packages.*

```bash
sudo apt-get install $(grep -vE "^\s*#" configuration/apt.txt | tr "\n" " ")
```

During installation MySQL you to enter a password for the user `root`.

## STEP 3.
*Creating a virtual environment.*

```bash
sudo pip install --upgrade pip
sudo pip install --upgrade virtualenv
sudo pip install --upgrade virtualenvwrapper
sudo echo "source /usr/local/bin/virtualenvwrapper.sh" >> ~/.bashrc
sudo echo "export WORKON_HOME="$HOME/venv"" >> ~/.bashrc
```

After the command, you must restart the console.

```bash
mkdir ~/venv
mkvirtualenv vboost
```
you must see: **(vboost)**user@user-pc:~$

## STEP 4.
*Getting the code.*

For [SSH](https://confluence.atlassian.com/display/BITBUCKET/Set+up+SSH+for+Mercurial):
```bash
hg clone ssh://hg@bitbucket.org/vboost/vboostoffice
```


## STEP 5.
*Сonfiguration database.*

```bash
mysql -u root -p -h localhost
CREATE DATABASE vboost;
GRANT ALL PRIVILEGES ON vboost.* TO 'vboost'@'localhost';
```

## STEP 6.
*Сonfiguration settings.*

See <project_dir>/vboostoffice/settings.
Folder contains following the next files:

* __init__.py (file are required to make Python treat the directories as containing packages)
* base.py (contains general settings for development.py and production.py)
* development.py (contains settings ONLY for development)
* local.py (contains local settings, **is not contained in SVN**)
* production.py (contains settings ONLY for production)
* local.default.py (blank for your local.py)

Rename `local.default.py` in local.py and add your local settings.
Example local.py:

```
from .development import *
TIME_ZONE = 'yourtimezone'
MEDIA_ROOT = '/path/'
MEDIA_URL = '/media/'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'vboost',                      # Or path to database file if using sqlite3.
        'USER': 'vboost',                      # Not used with sqlite3.
        'PASSWORD': '***',                  # Not used with sqlite3.
        'HOST': 'localhost',                      # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',                      # Set to empty string for default. Not used with sqlite3.
        'STORAGE_ENGINE': 'INNODB',
    },
}
```

## STEP 7. ##
*Install requirements, preparing system for running.*

```bash
pip install pycurl
pip install -r requirements.txt
```

## STEP 8. ##
*Migrate & Run.*

```
./manage.py migrate
```

run `./manage.py shell` and make
```
from django.contrib.sites.models import Site
Site.objects.create()
```

# TEST-SERVER #

