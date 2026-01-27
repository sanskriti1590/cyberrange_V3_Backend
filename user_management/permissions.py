from rest_framework.permissions import BasePermission

class IsAuthenticatedNotVerified(BasePermission):
    """
    Allows access only to authenticated users.
    """

    def has_permission(self, request, view):
        return bool(request._user and request._auth)


class CustomIsAuthenticated(BasePermission):
    """
    Allows access only to authenticated users.
    """

    def has_permission(self, request, view):
        return bool(request._user and request._auth and request._user['is_verified'])
    

class CustomIsAdmin(BasePermission):
    """
    Allows access only to authenticated Admin users.
    """

    def has_permission(self, request, view):
        return bool(request._user and request._auth and request._user['is_admin'] and request._user['is_verified'])
    

class CustomIsSuperAdmin(BasePermission):
    """
    Allows access only to authenticated SuperAdmin users.
    """

    def has_permission(self, request, view):
        return bool(request._user and request._auth and request._user['is_admin'] and request._user['is_verified'] and request._user['is_superadmin'])

