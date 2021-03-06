from django.core.exceptions import ImproperlyConfigured
from django.db.models.signals import pre_save, post_save, post_init
from django.dispatch import receiver
from django.conf import settings


if hasattr(settings, 'AUDIT_EXCLUDE') and hasattr(settings, 'AUDIT_INCLUDE'):
    raise ImproperlyConfigured("You can't set both AUDIT_EXCLUDE and AUDIT_INCLUDE")

AUDIT_CHANGES_EXCLUDE = \
    (
        'audit.models.LogItem',  # Do not log log items to prevent recursion
        'audit.models.FieldChange',  # Do not log field modifications to prevent recursion
        'django.contrib.sessions.models.Session',  # Session keys can not be stored in db (and history is unnecessary)
        'django.contrib.admin.models.LogEntry',  # No point in logging a log
        'django.contrib.auth.models.Permission',  # No point in logging permissions (auto-generated by Django)
        'django.contrib.contenttypes.models.ContentType'  # No point in logging content types (auto-generated by Django)
    ) + getattr(settings, 'AUDIT_CHANGES_EXCLUDE', ())
AUDIT_CHANGES_INCLUDE = getattr(settings, 'AUDIT_CHANGES_INCLUDE', ())
AUDIT_CHANGES_EXCLUDED_FIELD_TYPES = getattr(settings, 'AUDIT_CHANGES_EXCLUDED_FIELD_TYPES',
                                     'django.db.models.fields.related.AutoField')
AUDIT_CHANGES_EXCLUDED_FIELD_NAMES = getattr(settings, 'AUDIT_CHANGES_EXCLUDED_FIELD_NAMES', ())


def _ignore_model_audit(instance):
    """Determines whether the passed instance should be audited."""

    # If _no_audit is set on the object and has some True value
    if hasattr(instance, '_no_audit') and instance._no_audit:
        return True

    # Check if module is in the include/exclude list
    module = instance.__module__ + '.' + instance.__class__.__name__

    if AUDIT_CHANGES_INCLUDE:
        return module not in AUDIT_CHANGES_INCLUDE
    else:
        return module in AUDIT_CHANGES_EXCLUDE


def _ignore_field_audit(instance, field):
    field_module = field.__module__ + '.' + field.__class__.__name__
    field_name = instance.__module__ + '.' + instance.__class__.__name__ + '.' + field.name

    return field_module in AUDIT_CHANGES_EXCLUDED_FIELD_TYPES or field_name in AUDIT_CHANGES_EXCLUDED_FIELD_NAMES


@receiver(post_init, dispatch_uid='audit_post_init')
def initialize_audit(sender, instance, **kwargs):
    """Initializes all values of all fields of the instance into a _old attribute on the model."""

    if not _ignore_model_audit(instance):

        has_saved = getattr(instance, 'pk', None)
        value_dict = {}

        for field in instance._meta.fields:
            if not _ignore_field_audit(instance, field):
                if has_saved:
                    value_dict[field.name] = field.value_from_object(instance)
                else:
                    value_dict[field.name] = ''

        instance._old = value_dict


@receiver(pre_save, dispatch_uid='audit_pre_save')
def calculate_audit_differences(sender, instance, **kwargs):
    """Calculates the difference between the old  and the current instance and provides this in the _audit_changes
    attribute.
    """

    if not _ignore_model_audit(instance):
        changes = {}

        if hasattr(instance, '_old'):
            # Case I: old values were pre-computed by the post_init signal and are present in instance._old
            for field in instance._meta.fields:
                # Do not calculate a changeset if the field type is excluded, if the field name is excluded or the
                # field does not exist in the old instance.
                if not _ignore_field_audit(instance, field) and field.name in instance._old:
                    if instance._old[field.name] != field.value_from_object(instance):
                        changes[field.name] = (instance._old[field.name], field.value_from_object(instance))

        elif getattr(instance, 'pk', None):
            # Case II: old values are not present in instance._old, but the old version of the model can be retrieved
            # from the database.

            old_model = sender.objects.get(pk=instance.pk)

            for field in old_model._meta.fields:
                if not _ignore_field_audit(instance, field):
                    if field.value_from_object(old_model) != field.value_from_object(instance):
                        changes[field.name] = (field.value_from_object(old_model), field.value_from_object(instance))

        instance._audit_changes = changes


@receiver(post_save, dispatch_uid='audit_post_save')
def store_audit(sender, instance, created, raw, **kwargs):
    """Stores the audit information of the instance."""

    # Do not store the audit when the instance is ignored or the save is raw (i.e. batch).
    if not _ignore_model_audit(instance) and not raw:
        changes = getattr(instance, '_audit_changes', {})

        # Only store information when there are changes or the object is created.
        if created or changes:
            from audit.models import LogItem # prevent recursive imports

            actor = getattr(instance, '_audit_actor', None)
            code = created and LogItem.INSTANCE_CREATED or LogItem.INSTANCE_MODIFIED

            log = LogItem(related_object=instance, code=code, actor=actor)
            log.save(actor=actor)  # actor is passed because we can, but is not used
            log.create_field_changes(changes)


# Not set as receiver here, but by middleware.
def pass_audit_user(user, sender, instance, **kwargs):
    """Stores the passed user as the audit user on the created instance"""
    instance._audit_actor = user