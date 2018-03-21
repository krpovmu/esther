# -*- coding: utf-8 -*-
"""
Utilidades para ejecutar comandos.

Contiene código de Bitten (http://bitten.edgewall.org)

Copyright (C) 2005-2007 Christopher Lenz <cmlenz@gmx.de>
Copyright (C) 2007 Edgewall Software
All rights reserved.

http://svn.edgewall.org/repos/bitten/trunk/bitten/build/api.py

"""

#$Id$


import logging
import fnmatch
import os
import shlex
import time


_logger = logging.getLogger('esther.util')

# Tomado de Bitten (http://bitten.edgewall.org)
# 
# Copyright (C) 2005-2007 Christopher Lenz <cmlenz@gmx.de>
# Copyright (C) 2007 Edgewall Software
# All rights reserved.
#
# http://svn.edgewall.org/repos/bitten/trunk/bitten/build/api.py

def _combine(*iterables):
    iterables = [iter(iterable) for iterable in iterables]
    size = len(iterables)
    while True:
        to_yield = [None] * size
        for idx, iterable in enumerate(iterables):
            if iterable is None:
                continue
            try:
                to_yield[idx] = iterable.next()
            except StopIteration:
                iterables[idx] = None
        if not [iterable for iterable in iterables if iterable is not None]:
            break
        yield tuple(to_yield)


class CommandLine(object):
    """Simple helper for executing subprocesses."""

    def __init__(self, executable, args, input=None, cwd=None):
        """Initialize the CommandLine object.
        
        :param executable: the name of the program to execute
        :param args: a list of arguments to pass to the executable
        :param input: string or file-like object containing any input data for
                      the program
        :param cwd: the working directory to change to before executing the
                    command
        """
        self.executable = executable
        self.arguments = [str(arg) for arg in args]
        self.input = input
        self.cwd = cwd
        if self.cwd:
            assert os.path.isdir(self.cwd)
        self.returncode = None

    if os.name == 'nt': # windows

        def execute(self, timeout=None):
            """Execute the command, and return a generator for iterating over
            the output written to the standard output and error streams.
            
            :param timeout: number of seconds before the external process
                            should be aborted (not supported on Windows)
            """
            args = [self.executable] + self.arguments
            for idx, arg in enumerate(args):
                if arg.find(' ') >= 0:
                    args[idx] = '"%s"' % arg
            _logger.debug('Executing %s', args)

            if self.cwd:
                old_cwd = os.getcwd()
                os.chdir(self.cwd)

            import tempfile
            in_name = None
            if self.input:
                if isinstance(self.input, basestring):
                    in_file, in_name = tempfile.mkstemp(prefix='bitten_',
                                                        suffix='.pipe')
                    os.write(in_file, self.input)
                    os.close(in_file)
                    in_redirect = '< "%s" ' % in_name
                else:
                    in_redirect = '< "%s" ' % self.input.name
            else:
                in_redirect = ''

            out_file, out_name = tempfile.mkstemp(prefix='bitten_',
                                                  suffix='.pipe')
            os.close(out_file)
            err_file, err_name = tempfile.mkstemp(prefix='bitten_',
                                                  suffix='.pipe')
            os.close(err_file)

            try:
                cmd = '( %s ) > "%s" %s 2> "%s"' % (' '.join(args), out_name,
                                                    in_redirect, err_name)
                self.returncode = os.system(cmd)
                _logger.debug('Exited with code %s', self.returncode)

                out_file = file(out_name, 'r')
                err_file = file(err_name, 'r')
                out_lines = out_file.readlines()
                err_lines = err_file.readlines()
                out_file.close()
                err_file.close()
            finally:
                if in_name:
                    os.unlink(in_name)
                if out_name:
                    os.unlink(out_name)
                if err_name:
                    os.unlink(err_name)
                if self.cwd:
                    os.chdir(old_cwd)

            for out_line, err_line in _combine(out_lines, err_lines):
                yield out_line and out_line.rstrip().replace('\x00', ''), \
                      err_line and err_line.rstrip().replace('\x00', '')

    else: # posix

        def execute(self, timeout=None):
            """Execute the command, and return a generator for iterating over
            the output written to the standard output and error streams.
            
            :param timeout: number of seconds before the external process
                            should be aborted (not supported on Windows)
            """
            import popen2, select
            if self.cwd:
                old_cwd = os.getcwd()
                os.chdir(self.cwd)

            _logger.debug('Executing %s', [self.executable] + self.arguments)
            pipe = popen2.Popen3([self.executable] + self.arguments,
                                 capturestderr=True)
            if self.input:
                if isinstance(self.input, basestring):
                    in_data = self.input
                else:
                    in_data = self.input.read()
            else:
                pipe.tochild.close()
                in_data = ''

            out_data, err_data = [], []
            in_eof = out_eof = err_eof = False
            if not in_data:
                in_eof = True
            while not out_eof or not err_eof:
                readable = [pipe.fromchild] * (not out_eof) + \
                           [pipe.childerr] * (not err_eof)
                writable = [pipe.tochild] * (not in_eof)
                ready = select.select(readable, writable, [], timeout)
                if not (ready[0] or ready[1]):
                    raise TimeoutError('Command %s timed out' % self.executable)
                if pipe.tochild in ready[1]:
                    sent = os.write(pipe.tochild.fileno(), in_data)
                    in_data = in_data[sent:]
                    if not in_data:
                        pipe.tochild.close()
                        in_eof = True
                if pipe.fromchild in ready[0]:
                    data = os.read(pipe.fromchild.fileno(), 1024)
                    if data:
                        out_data.append(data)
                    else:
                        out_eof = True
                if pipe.childerr in ready[0]:
                    data = os.read(pipe.childerr.fileno(), 1024)
                    if data:
                        err_data.append(data)
                    else:
                        err_eof = True
                out_lines = self._extract_lines(out_data)
                err_lines = self._extract_lines(err_data)
                for out_line, err_line in _combine(out_lines, err_lines):
                    yield out_line, err_line
                time.sleep(.1)
            self.returncode = pipe.wait()
            _logger.debug('%s exited with code %s', self.executable,
                      self.returncode)

            if self.cwd:
                os.chdir(old_cwd)

    def _extract_lines(self, data):
        extracted = []
        def _endswith_linesep(string):
            for linesep in ('\n', '\r\n', '\r'):
                if string.endswith(linesep):
                    return True
        buf = ''.join(data)
        lines = buf.splitlines(True)
        if len(lines) > 1:
            extracted += lines[:-1]
            if _endswith_linesep(lines[-1]):
                extracted.append(lines[-1])
                buf = ''
            else:
                buf = lines[-1]
        elif _endswith_linesep(buf):
            extracted.append(buf)
            buf = ''
        data[:] = [buf] * bool(buf)

        return [line.rstrip() for line in extracted]

def svn_export(url, destino, rev=None, username=None, password=None, force=False, eol=None):
    executable = 'svn'

    args = ['export']
    
    if rev:
        args.append('-r %s' % rev)
    
    if username:
        args.append('--username=%s' % username)

    if password:
        args.append('--password=%s' % password)
    
    if eol:
        args.append('--native-eol %s' % eol)
    
    if force:
        args.append('--force')
    
    args.append(url)
    args.append(destino)
    
    cmd = CommandLine(executable, args)
    salida = list(cmd.execute())

    for s in salida:
        _logger.debug('svn export: %s', s)

    if cmd.returncode != 0:
        raise Exception("Error al ejecutar svn. Estado=%s. %s " % (cmd.returncode, salida))
   



def rsync(dir_origen, dir_destino, excluir=[], comprimir=True, ssh=True, borrar=False, archive=True, adicionales=''):
    """
    Wrapper para ejecutar rsync
    
    :param dir_origen: Directorio de origen.
    :param dir_destino: Directorio de origen.
    :param excluir: Lista de patrones que se deben excluir.
    :param comprimir: Comprimir los datos. Opción '-z'
    :param ssh: Utilizar SSH como shell remoto. Opción '-e ssh'
    :param borrar: Borrar los archivos del destino que no se encuentren en el origen. Opción: '--delete'
    :param archive: Opción '-a'
    :param adicionales: Argumentos adicionales. 
    
    """
    executable = 'rsync'

    args = []

    if ssh:
        args.append('-e ssh')

    if archive:
        args.append('-a')

    if comprimir:
        args.append('-z')

    if borrar:
        args.append('--delete')

    #Excluir
    if excluir:
        args.extend(["--exclude='%s'" % patron for patron in excluir])

    if adicionales:
        args.append(adicionales)

    args.append(dir_origen)
    args.append(dir_destino)
    
    cmd = CommandLine(executable, args)
    salida = list(cmd.execute())
    

    for s in salida:
        _logger.debug('rsync: %s', s)

    if cmd.returncode != 0:
        raise Exception("Error al ejecutar rsync. Estado=%s. %s " % (cmd.returncode, salida))
   
