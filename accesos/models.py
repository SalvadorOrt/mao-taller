from django.contrib.auth.models import Group, Permission


# =========================================================
# ROL
# =========================================================

class Rol(Group):
    """
    Un Rol de MAO utiliza internamente los Groups de Django.

    No crea una tabla nueva.
    """
    class Meta:
        proxy = True
        verbose_name = "Rol"
        verbose_name_plural = "Roles"
        ordering = ["name"]

    def __str__(self):
        return self.name


# =========================================================
# PERMISO
# =========================================================

class Permiso(Permission):
    """
    Representación de los permisos de Django dentro
    del módulo de accesos de MAO.

    No crea una tabla nueva.
    """
    class Meta:
        proxy = True
        verbose_name = "Permiso"
        verbose_name_plural = "Permisos"

    def __str__(self):
        return self.name