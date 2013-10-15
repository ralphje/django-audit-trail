from django.db.models.signals import post_init
from django.utils.functional import curry
from audit.signals import pass_audit_user


class AuditMiddleware(object):
    """Middleware that registers a post init handler for all models to ensure the actor of a model change is logged
    properly.
    """
    def process_request(self, request):
        if hasattr(request, 'user') and request.user.is_authenticated():
            user = request.user
        else:
            user = None

        user_passer = curry(pass_audit_user, user)
        post_init.connect(user_passer, weak=False, dispatch_uid=('audit_post_init_middleware', request))