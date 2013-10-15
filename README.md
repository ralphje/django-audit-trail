django-audit-trail
==================

Django app that allows you to maintain an entire object history and audit log of every activity and modification in your Django app. Without too much effort, this app maintains a list of all changes that occur to all objects in your database. You can exclude models or specific fields from being logged.

In contrast to other audit apps, this app only utilizes two tables for audit trails. This has the advantage of super easy setup and a clean database, but has the disadvantage that all values in your models are converted to string before being saved.

django-audit-trail should run on the latest Django stable. It is not released yet.

Installation
------------

Include ``audit`` in your ``INSTALLED_APPS`` setting and run ``manage.py syncdb`` to install the required tables (there are two).

To track the actor (user) performing an action automatically, you should add ``audit.middleware.AuditMiddleware`` to your ``MIDDLEWARE_CLASSES`` setting, below the AuthenticationMiddleware (but it does not need to be directly below it, it should just not be before it).

If you wish to track actors manually, you should inherit your models from ``audit.models.Model``, which adds an additional keyword argument to the save method, allow you to pass an actor.

By default, the app tracks modifications on all models, except its own models, sessions.Session, admin.LogEntry, auth.Permission and contenttypes.ContentType. Additional modules (full paths, i.e. module.class) can be added via the ``AUDIT_CHANGES_EXCLUDE`` setting. Instead, you may also specify the ``AUDIT_CHANGES_INCLUDE`` setting, to specify which models you wish to track. (You can not specify both.)

Additionally, you can specify which field names you do not wish to track via the ``AUDIT_CHANGES_EXCLUDED_FIELD_NAMES`` setting. Add fields by specifying them as ``model.field``, e.g. ``audit.models.LogItem.created_at``. Field types can be excluded via ``AUDIT_CHANGES_EXCLUDED_FIELD_TYPES``, which may be useful when you use a custom field that is not serializable. AutoField is excluded by default.

Usage
-----

Any audit logging is entirely automatic. However, if you are using models in a non-request context, or have not loaded the middleware, and do want to store the actor performing an action, you should inherit your models from ``audit.models.Model`` and replace all calls to ``save()`` with ``save(actor=user)``. Saving a form can be done by calling ``audit.save_form(form, actor=actor)``.

Reading the audit log in your code can be done by searching for the correct LogItem (it uses a GenericForeignKey). Modifications can be found in the fieldchange_set. Every modification contains an old_value and a new_value, both of which are always set if known.

Be warned that the two tables can grow exponentially and you should use a proper DB setup that can handle this bulk of data. (Every value is stored multiple times: in the original table, in the new_value and after some time also in the old_value).

Internals
---------

Please refrain from using any internals.

Internally, the app listens to three signals: post_init, pre_save and post_save. In the post_init phase, the model is analyzed and all values are stored in a dict on the object in the attribute ``_old``. In the pre_save signal, the changeset is calculated and stored in ``_audit_changes`` attribute. Finally, the post_save signal converts this to a database entry.

The middleware adds a ``_audit_actor`` attribute to every model created after the middleware is called by creating a custom post init signal. This attribute could be assigned at any other place.

Future Work
-----------
* Tracking instance views by a user
* Tracking logins and logouts as an additional option
* Custom admin views (work has started, but does not what I want it to do yet)
* Prevent duplicate data saving; we should only store old_value if this was not the previous new_value.