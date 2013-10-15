from django.conf.urls import patterns, url
from django.contrib import admin
from django.contrib.admin.util import unquote
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils.encoding import force_text
from django.utils.text import capfirst
from audit.models import LogItem, FieldChange


class AuditModelAdmin(admin.ModelAdmin):
    def get_urls(self):
        urls = super(AuditModelAdmin, self).get_urls()
        info = self.model._meta.app_label, self.model._meta.module_name

        urls += patterns('',
            url(r'^(.+)/audit/$', self.admin_site.admin_view(self.audit_view), name='%s_%s_audit' % info),
        )
        return urls

    def audit_view(self, request, object_id, extra_context=None):
        from audit.models import LogItem
        # First check if the user can see this history.
        model = self.model
        obj = get_object_or_404(self.get_queryset(request), pk=unquote(object_id))

        if not self.has_change_permission(request, obj):
            raise PermissionDenied

        # Then get the history for this object.
        opts = model._meta
        app_label = opts.app_label
        action_list = LogItem.objects.filter(
            object_id=unquote(object_id),
            content_type__id__exact=ContentType.objects.get_for_model(model).id
        ).select_related().order_by('action_time')

        context = dict(self.admin_site.each_context(),
                       title=_('Change history: %s') % force_text(obj),
                       action_list=action_list,
                       module_name=capfirst(force_text(opts.verbose_name_plural)),
                       object=obj,
                       app_label=app_label,
                       opts=opts,
                       preserved_filters=self.get_preserved_filters(request),
        )
        context.update(extra_context or {})
        return TemplateResponse(request, self.object_history_template or [
            "admin/%s/%s/audit_history.html" % (app_label, opts.module_name),
            "admin/%s/audit_history.html" % app_label,
            "admin/audit_history.html"
        ], context, current_app=self.admin_site.name)


class FieldChangeInline(admin.TabularInline):
    model = FieldChange
    fk_name = 'logitem'
class LogItemAdmin(AuditModelAdmin):
    inlines = (FieldChangeInline, )
admin.site.register(LogItem, LogItemAdmin)
