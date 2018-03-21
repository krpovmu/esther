# -*- coding: utf-8 -*-
"""
"""

#$Id$

__docformat__ = 'restructuredtext es'

try:
    __version__ = __import__('pkg_resources').get_distribution('esther').version
except Exception:
    pass


class Ambiente:
    """
    Un Ambiente agrupa las opciones de configuracion de una aplicacion
    en un conjunto de servidores.
    """
    def __init__(self, nombre, ruta, usuario, servidores):
        self.nombre = nombre
        self.ruta = ruta
        self.usuario = usuario
        self.servidores = servidores 

class Proyecto:
    def __init__(self, nombre, svn_url, ambientes, comandos_pre = [], comandos_post = []):
        self.nombre = nombre
        self.svn_url = svn_url
        self.svn_user = None
        self.svn_password = None
        self.ambientes = ambientes
        self.comandos_pre = comandos_pre
        self.comandos_post = comandos_post

