# -*- coding: utf-8 -*-
"""


"""

#$Id$

import os
import shutil
import logging
import tempfile
from optparse import OptionParser

import esther

import util

_logger = logging.getLogger('esther')

def instalar(proyecto, ambiente, rutasvn = '/', dir_trabajo=None):
    """
    
    """
    if not dir_trabajo:
        dir_trabajo = tempfile.mkdtemp(prefix='esther')
    elif not os.path.exists(dir_trabajo):
        os.makedirs(dir_trabajo) 
    
    dir_destino = os.path.join(dir_trabajo, proyecto.nombre, ambiente.nombre)
    if os.path.isdir(dir_destino):
        shutil.rmtree(dir_destino)
    os.makedirs(dir_destino)

    actualizar(proyecto, ambiente, dir_destino, rutasvn)
    comandos(proyecto, proyecto.comandos_pre, dir_destino)
    copiar(dir_destino, ambiente)
    comandos(proyecto, proyecto.comandos_post, dir_destino)
    shutil.rmtree(dir_trabajo)

def comandos(proyecto, comandos, ruta):
    for cmd in comandos:
        cmd = cmd % ({'buildpath' : ruta})
        os.system(cmd)
        _logger.debug(cmd)
        

def copiar(ruta, ambiente):
    """
    Sincroniza los servidores con la copia local
    """
    if not ruta.endswith('/'):
        ruta = ruta + '/'
    
    dir_destino = "%(usuario)s@%(servidor)s:%(ruta)s"
    excluir = []
    for serv in ambiente.servidores:
        destino = dir_destino % {
            'usuario': ambiente.usuario, 
            'servidor': serv, 
            'ruta': ambiente.ruta}
        util.rsync(ruta, destino, excluir, borrar=True)

def actualizar(proyecto, ambiente, dir_destino, rutasvn = '/'):
    """
    Actualiza la copia local con los cambios del repositorio
    
    :param proyecto: El proyecto que se instalará
    :param ambiente: La configuración del ambiente en donde se instala
    :param ruta: La ruta dentro del control de versiones que se exportará.
                Opcional. Por omisión es '/'
    """


    ruta = proyecto.svn_url + rutasvn

    logging.debug('Iniciando export')
    
    util.svn_export(ruta, dir_destino, force=True,
                    username=proyecto.svn_user, 
                    password=proyecto.svn_password)
    
    logging.debug('Export terminado')


def _actualizar(proyecto, ambiente, dir_destino, rutasvn = '/'):
    """
    Actualiza la copia local con los cambios del repositorio
    
    :param proyecto: El proyecto que se instalará
    :param ambiente: La configuración del ambiente en donde se instala
    :param ruta: La ruta dentro del control de versiones que se exportará.
                Opcional. Por omisión es '/'
    """
    cliente = pysvn.Client()
    
    if proyecto.svn_user:
        def _login(realm, username, may_save):
            return  (True, proyecto.svn_user, proyecto.svn_password, True)

        cliente.callback_get_login = _login

    ruta = proyecto.svn_url + rutasvn
    rev = pysvn.Revision(pysvn.opt_revision_kind.head)

    logging.debug('Iniciando export')
    rev_exportada = cliente.export(ruta,
        dir_destino,
        force=True,
        revision=rev,
        native_eol=None,
        ignore_externals=False,
        recurse=True,
        )
    logging.debug('Export %s' % rev_exportada)
    print rev_exportada


def cargar_configuracion(archivo):
    """
    Lee el archivo de configuración y devuelve una lista de objetos Proyecto
    con los datos definidos en ese archivo.
    
    :param archivo: El nombre del archivo de configuración
    """
    f = open(archivo, 'r')
    try:
	proyectos = eval(f.read())
	conf = {}
	for nombre in proyectos:
            info = proyectos[nombre]
            ambientes = dict([(id, esther.Ambiente(id,
                                            info['ambientes'][id]['ruta'],
                                            info['ambientes'][id]['usuario'],
                                            info['ambientes'][id]['servidores'])) 
                              for id in info['ambientes']])
            
            proyecto = esther.Proyecto(nombre, info['svn_url'], ambientes)
            proyecto.svn_user = info.get('svn_user')
            proyecto.svn_password = info.get('svn_password')

            proyecto.comandos_pre = info.get('comandos_pre', [])
            proyecto.comandos_post = info.get('comandos_post', [])

            conf[nombre] = proyecto
        return conf
    except Exception, e:
        logging.exception("Error al leer el archivo de configuracion")
        raise Exception("Error al leer el archivo de configuracion (%s)" % e.message)


def main():
    uso = """Uso: %prog [opciones] proyectos-config proyecto ambiente rutasvn
    
    proyectos-config    Archivo de configuracion de proyectos
    proyecto            Nombre de proyecto a instalar
    ambiente            Ambiente del proyecto a instalar
    rutasvn             La ruta dentro del control de versiones que se instalara

    
    """
    parser = OptionParser(uso)
    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False,
                      help="Presenta mensajes adicionales en la salida estado.")

    parser.add_option("-d", "--directorio-trabajo",
                      action="store", dest="dir_trabajo", default=None,
                      help="Directorio de trabajo en donde de extraen los archivos temporales.")

    options, args = parser.parse_args()
    if len(args) != 4:
        parser.error('Numero incorrecto de argumentos')

    log_level = options.verbose and logging.DEBUG or logging.INFO
    logging.basicConfig(level=log_level, 
                        format='%(asctime)s %(levelname)s %(name)-12s %(message)s')

    configuracion = cargar_configuracion(args[0])
    proyecto = configuracion.get(args[1])
    ambiente = proyecto.ambientes.get(args[2])
    ruta = args[3]

    instalar(proyecto, ambiente, ruta, dir_trabajo=options.dir_trabajo)

if __name__ == '__main__':
    main()
