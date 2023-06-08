import logging

from celery import Task
from .models import LoggingModel


class LoggingTask(Task):
    """On failure, this task adds an admin history item for the model."""

    abstract = True

    # We don't want to retry tasks eternally
    max_retries = 200

    # But sequential retries should be separated by a timeout
    default_retry_delay = 60

    # We generally do not need task results...
    # ignore_result = True

    # Unless they are errors.
    store_errors_even_if_ignored = True

    # Which also lead to sending emails.
    send_error_emails = True

    # A task is marked completed after it is executed.
    # On daemon crash or system reboot it may lead to repeating the task,
    # which is not too bad.
    acks_late = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        If a report fails processing, a record is saved
        in the report admin history.
        """

        instance = args[0]

        assert isinstance(
            instance, LoggingModel
        ), "%s should be instance of LoggingModel" % instance

        # notify the instance itself
        instance.log_action(str(exc))

        instance.state = 'error'
        instance.save()

        # To Sentry
        logger = logging.getLogger(__name__)
        logger.error(str(exc), exc_info=einfo, extra={
            'instance': instance,
        })
