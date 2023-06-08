from .tasks import *
#import tasks    # Very important. Without this line. "tasks" module does
                # not get imported and package workflow fails.
default_app_config = 'packages.apps.PackagesAppConfig'
