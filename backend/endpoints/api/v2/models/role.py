"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Tiago Teixeira  (tiago.teixeira@mov.ai) - 2020

   Role Model (only of name)
"""

from typing import Dict

from movai.data import scopes

from .model import Model

class Role(Model):
    """ Role Model (only of name) """

    # default __init__

    def create_permission(self, resource: str, permission: str) -> bool:
        """ Creates a new role permission

            Doesn't write on storage, call `.write()` to save
        """
        try:
            self.Resources[resource.capitalize()].append(permission.lower())
        except KeyError:    # resource doesn't exist
            return False

        return True

    def delete_permission(self, resource: str, permission: str) -> bool:
        """ Delete role permission

            Doesn't write to storage, call `.write()` to save
        """
        try:
            self.Resources[resource.capitalize()].remove(permission.lower())
        except KeyError:
            # KeyError: no such key resource
            return False
        except ValueError:
            # ValueError: permission not found on list (we don't care)
            pass
        return True

    @staticmethod
    def create(*, name: str, resources: Dict) -> bool:
        """ Create a new role """
        try:
            name = name.lower()
            role = scopes().create('Role', name)
            role.Label = name
            role.Resources = resources
            role.write()
        except ValueError:
            # ValueError: scope already exists
            return False
        return True

    @staticmethod
    def update(*, name: str, resources: Dict) -> bool:
        """ Reset role data """
        try:
            name = name.lower()
            role = scopes.from_path(name, scope='Role')
            role.Label = name
            role.Resources = resources
            role.write()    # or shall we not write?
        except KeyError:
            # KeyError: scope does not exist
            return False

        return True

Model.register_model_class('Role', Role)
