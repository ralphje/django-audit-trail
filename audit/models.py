from django.contrib.auth.models import User
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import ugettext_lazy as _
import signals


class Model(models.Model):
    """Overrides the save attribute of the default django.db.models.Model to allow actors to be passed."""

    def save(self, actor=None, *args, **kwargs):
        self._audit_actor = actor
        super(Model, self).save(*args, **kwargs)


class LogItem(Model):
    DEBUG = 10
    INFO = 20
    SUCCESS = 25
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

    LOG_LEVEL = (
        (CRITICAL, _('Critical')),
        (ERROR, _('Error')),
        (WARNING, _('Warning')),
        (SUCCESS, _('Success')),
        (INFO, _('Info')),
        (DEBUG, _('Debug'))
    )

    INSTANCE_CREATED = 10001
    INSTANCE_MODIFIED = 10002
    INSTANCE_DELETED = 10003 # not used.

    LOG_CODES = (
        (INSTANCE_CREATED, _('Object created.')),
        (INSTANCE_MODIFIED, _('Object modified.')),
        (INSTANCE_DELETED, _('Object deleted.')),
    )

    content_type = models.ForeignKey(ContentType, blank=True, null=True, verbose_name=_('content type'))
    object_id = models.PositiveIntegerField(_('object id'), blank=True, null=True)
    logged_at = models.DateTimeField(_('logged at'), auto_now_add=True)
    actor = models.ForeignKey(User, blank=True, null=True, verbose_name=_('actor'))
    code = models.PositiveIntegerField(_('code'))
    level = models.PositiveSmallIntegerField(_('level'), choices=LOG_LEVEL, default=INFO)
    context = models.TextField(_('context'), blank=True)

    related_object = generic.GenericForeignKey('content_type', 'object_id')
    related_object.short_description = _('Related object')

    def get_message(self):
        return LogItem.LOG_CODES[self.code]

    def create_field_changes(self, changes):
        """Adds the field changes of the attached changes dict to this log item."""
        for field, values in changes.iteritems():
            self.fieldchange_set.create(field=field, old_value=values[0], new_value=values[1])

    def __unicode__(self):
        return "[%s] %s" % (self.code, self.level, )

    class Meta:
        verbose_name = _("log item")
        verbose_name_plural = _("log items")
        ordering = ('-logged_at', '-id')


class FieldChange(Model):
    logitem = models.ForeignKey(LogItem, verbose_name=_('log item'))
    field = models.CharField(_('field'), max_length=20)
    old_value = models.CharField(_('old value'), max_length=255, blank=True, null=True)
    new_value = models.CharField(_('new value'), max_length=255, blank=True, null=True)

    def __unicode__(self):
        return "%s (%s -> %s)" % (self.field, self.old_value, self.new_value)

    class Meta:
        verbose_name = _("field change")
        verbose_name_plural = _("field changes")
        ordering = ('field', )
