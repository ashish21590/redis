#!/usr/bin/python

""" redis.py - A client for the Redis daemon.

"""

__author__ = "Ludovico Magnocavallo <ludo\x40qix\x2eit>"
__copyright__ = "Copyright 2009, Ludovico Magnocavallo"
__license__ = "MIT"
__version__ = "0.3"
__revision__ = "$LastChangedRevision$"[22:-2]
__date__ = "$LastChangedDate$"[18:-2]


import socket


BUFSIZE = 4096


class RedisError(Exception): pass
class ConnectionError(RedisError): pass
class ResponseError(RedisError): pass
class InvalidResponse(RedisError): pass
class InvalidData(RedisError): pass


class Redis(object):
    """The main Redis client.
    """
    
    def __init__(self, host=None, port=None, timeout=None):
        self.host = host or 'localhost'
        self.port = port or 6379
        if timeout:
            socket.setdefaulttimeout(timeout)
        self._sock = None
        self._fp = None
        
    def _write(self, s):
        """
        >>> r = Redis()
        >>> r.connect()
        >>> r._sock.close()
        >>> try:
        ...     r._write('pippo')
        ... except ConnectionError, e:
        ...     print e
        Error 9 while writing to socket. Bad file descriptor.
        >>>
        >>> 
        """
        try:
            self._sock.sendall(s)
        except socket.error, e:
            if e.args[0] == 32:
                # broken pipe
                self.disconnect()
            raise ConnectionError("Error %s while writing to socket. %s." % tuple(e.args))
            
    def _read(self):
        try:
            return self._fp.readline()
        except socket.error, e:
            if e.args and e.args[0] == errno.EAGAIN:
                return
            self.disconnect()
            raise ConnectionError("Error %s while reading from socket. %s." % tuple(e.args))
        if not data:
            self.disconnect()
            raise ConnectionError("Socket connection closed when reading.")
        return data
    
    def ping(self):
        """
        >>> r = Redis()
        >>> r.ping()
        'PONG'
        >>> 
        """
        self.connect()
        self._write('PING\r\n')
        return self._get_simple_response()
    
    def set(self, name, value, preserve=False):
        """
        >>> r = Redis()
        >>> r.set('a', 'pippo')
        'OK'
        >>> try:
        ...     r.set('a', u'pippo \u3235')
        ... except InvalidData, e:
        ...     print e
        Error encoding unicode value for key 'a': 'ascii' codec can't encode character u'\u3235' in position 15: ordinal not in range(128).
        >>> r.set('b', 105.2)
        'OK'
        >>> r.set('b', 'xxx', preserve=True)
        0
        >>> r.get('b')
        '105.2'
        >>> 
        """
        self.connect()
        # the following will raise an error for unicode values that can't be encoded to ascii
        # we could probably add an 'encoding' arg to init, but then what do we do with get()?
        # convert back to unicode? and what about ints, or pickled values?
        try:
            value = value if isinstance(value, basestring) else str(value)
            self._write('%s %s %s\r\n%s\r\n' % (
                'SETNX' if preserve else 'SET', name, len(value), value
            ))
        except UnicodeEncodeError, e:
            raise InvalidData("Error encoding unicode value for key '%s': %s." % (name, e))
        return self._get_numeric_response() if preserve else self._get_simple_response()
    
    def get(self, name):
        """
        >>> r = Redis()
        >>> r.set('a', 'pippo'), r.set('b', 15), r.set('c', '\\r\\naaa\\nbbb\\r\\ncccc\\nddd\\r\\n'), r.set('d', '\\r\\n')
        ('OK', 'OK', 'OK', 'OK')
        >>> r.get('a')
        'pippo'
        >>> r.get('b')
        '15'
        >>> r.get('d')
        '\\r\\n'
        >>> r.get('b')
        '15'
        >>> r.get('c')
        '\\r\\naaa\\nbbb\\r\\ncccc\\nddd\\r\\n'
        >>> r.get('c')
        '\\r\\naaa\\nbbb\\r\\ncccc\\nddd\\r\\n'
        >>> r.get('ajhsd')
        >>> 
        """
        self.connect()
        self._write('GET %s\r\n' % name)
        return self._get_value()
    
    def incr(self, name, amount=1):
        """
        >>> r = Redis()
        >>> r.delete('a')
        1
        >>> r.incr('a')
        1
        >>> r.incr('a')
        2
        >>> r.incr('a', 2)
        4
        >>>
        """
        self.connect()
        if amount == 1:
            self._write('INCR %s\r\n' % name)
        else:
            self._write('INCRBY %s %s\r\n' % (name, amount))
        return self._get_numeric_response()

    def decr(self, name, amount=1):
        """
        >>> r = Redis()
        >>> if r.get('a'):
        ...     r.delete('a')
        ... else:
        ...     print 1
        1
        >>> r.decr('a')
        -1
        >>> r.decr('a')
        -2
        >>> r.decr('a', 5)
        -7
        >>> 
        """
        self.connect()
        if amount == 1:
            self._write('DECR %s\r\n' % name)
        else:
            self._write('DECRBY %s %s\r\n' % (name, amount))
        return self._get_numeric_response()
    
    def exists(self, name):
        """
        >>> r = Redis()
        >>> r.exists('dsjhfksjdhfkdsjfh')
        0
        >>> r.set('a', 'a')
        'OK'
        >>> r.exists('a')
        1
        >>>
        """
        self.connect()
        self._write('EXISTS %s\r\n' % name)
        return self._get_numeric_response()

    def delete(self, name):
        """
        >>> r = Redis()
        >>> r.delete('dsjhfksjdhfkdsjfh')
        0
        >>> r.set('a', 'a')
        'OK'
        >>> r.delete('a')
        1
        >>> r.exists('a')
        0
        >>> r.delete('a')
        0
        >>> 
        """
        self.connect()
        self._write('DEL %s\r\n' % name)
        return self._get_numeric_response()

    def key_type(self, name):
        """
        Not yet implemented.
        """
        self.connect()
        self._write('TYPE %s\r\n' % name)
        return self._get_simple_response()
    
    def keys(self, pattern):
        """
        >>> r = Redis()
        >>> r.set('a', 'a')
        'OK'
        >>> r.keys('a*')
        ['a']
        >>> r.set('a2', 'a')
        'OK'
        >>> r.keys('a*')
        ['a', 'a2']
        >>> r.delete('a2')
        1
        >>> r.keys('sjdfhskjh*')
        []
        >>>
        """
        self.connect()
        self._write('KEYS %s\r\n' % pattern)
        return self._get_value().split()
    
    def randomkey(self):
        """
        >>> r = Redis()
        >>> r.set('a', 'a')
        'OK'
        >>> isinstance(r.randomkey(), str)
        True
        >>> 
        """
        #raise NotImplementedError("Implemented but buggy, do not use.")
        self.connect()
        self._write('RANDOMKEY\r\n')
        data = self._read().strip()
        self._check_for_error(data)
        return data
    
    def rename(self, src, dst, preserve=False):
        """
        >>> r = Redis()
        >>> try:
        ...     r.rename('a', 'a')
        ... except ResponseError, e:
        ...     print e
        src and dest key are the same
        >>> r.rename('a', 'b')
        'OK'
        >>> try:
        ...     r.rename('a', 'b')
        ... except ResponseError, e:
        ...     print e
        no such key
        >>> r.set('a', 1)
        'OK'
        >>> r.rename('b', 'a', preserve=True)
        0
        >>> 
        """
        self.connect()
        if preserve:
            self._write('RENAMENX %s %s\r\n' % (src, dst))
            return self._get_numeric_response()
        else:
            self._write('RENAME %s %s\r\n' % (src, dst))
            return self._get_simple_response().strip()
    
    def push(self, name, value, tail=False):
        """
        >>> r = Redis()
        >>> r.delete('l')
        1
        >>> r.push('l', 'a')
        'OK'
        >>> r.set('a', 'a')
        'OK'
        >>> try:
        ...     r.push('a', 'a')
        ... except ResponseError, e:
        ...     print e
        push against existing key not holding a list
        >>> 
        """
        self.connect()
        # same considerations on unicode as in set() apply here
        try:
            value = value if isinstance(value, basestring) else str(value)
            self._write('%s %s %s\r\n%s\r\n' % (
                'LPUSH' if tail else 'RPUSH', name, len(value), value
            ))
        except UnicodeEncodeError, e:
            raise InvalidData("Error encoding unicode value for element in list '%s': %s." % (name, e))
        return self._get_simple_response()
    
    def llen(self, name):
        """
        >>> r = Redis()
        >>> r.delete('l')
        1
        >>> r.push('l', 'a')
        'OK'
        >>> r.llen('l')
        1
        >>> r.push('l', 'a')
        'OK'
        >>> r.llen('l')
        2
        >>> 
        """
        self.connect()
        self._write('LLEN %s\r\n' % name)
        return self._get_numeric_response()

    def lrange(self, name, start, end):
        """
        >>> r = Redis()
        >>> r.delete('l')
        1
        >>> r.lrange('l', 0, 1)
        []
        >>> r.push('l', 'aaa')
        'OK'
        >>> r.lrange('l', 0, 1)
        ['aaa']
        >>> r.push('l', 'bbb')
        'OK'
        >>> r.lrange('l', 0, 0)
        ['aaa']
        >>> r.lrange('l', 0, 1)
        ['aaa', 'bbb']
        >>> r.lrange('l', -1, 0)
        []
        >>> r.lrange('l', -1, -1)
        ['bbb']
        >>> 
        """
        self.connect()
        self._write('LRANGE %s %s %s\r\n' % (name, start, end))
        results = list()
        try:
            num = self._get_numeric_response(allow_negative=False)
        except InvalidResponse, e:
            if e.args[1] == 'nil':
                return results
            raise
        while num:
            results.append(self._get_value())
            num -= 1
        return results
        
    def ltrim(self, name, start, end):
        """
        >>> r = Redis()
        >>> r.delete('l')
        1
        >>> try:
        ...     r.ltrim('l', 0, 1)
        ... except ResponseError, e:
        ...     print e
        no such key
        >>> r.push('l', 'aaa')
        'OK'
        >>> r.push('l', 'bbb')
        'OK'
        >>> r.push('l', 'ccc')
        'OK'
        >>> r.ltrim('l', 0, 1)
        'OK'
        >>> r.llen('l')
        2
        >>> r.ltrim('l', 99, 95)
        'OK'
        >>> r.llen('l')
        0
        >>> 
        """
        self.connect()
        self._write('LTRIM %s %s %s\r\n' % (name, start, end))
        return self._get_simple_response()
    
    def lindex(self, name, index):
        """
        >>> r = Redis()
        >>> res = r.delete('l')
        >>> r.lindex('l', 0)
        >>> r.push('l', 'aaa')
        'OK'
        >>> r.lindex('l', 0)
        'aaa'
        >>> r.lindex('l', 2)
        >>> r.push('l', 'ccc')
        'OK'
        >>> r.lindex('l', 1)
        'ccc'
        >>> r.lindex('l', -1)
        'ccc'
        >>> 
        """
        self.connect()
        self._write('LINDEX %s %s\r\n' % (name, index))
        return self._get_value()
        
    def pop(self, name, tail=False):
        """
        >>> r = Redis()
        >>> r.delete('l')
        1
        >>> r.pop('l')
        >>> r.push('l', 'aaa')
        'OK'
        >>> r.push('l', 'bbb')
        'OK'
        >>> r.pop('l')
        'aaa'
        >>> r.pop('l')
        'bbb'
        >>> r.pop('l')
        >>> r.push('l', 'aaa')
        'OK'
        >>> r.push('l', 'bbb')
        'OK'
        >>> r.pop('l', tail=True)
        'bbb'
        >>> r.pop('l')
        'aaa'
        >>> r.pop('l')
        >>> 
        """
        self.connect()
        self._write('%s %s\r\n' % ('RPOP' if tail else 'LPOP', name))
        return self._get_value()
    
    def lset(self, name, index, value):
        """
        >>> r = Redis()
        >>> r.delete('l')
        1
        >>> try:
        ...     r.lset('l', 0, 'a')
        ... except ResponseError, e:
        ...     print e
        no such key
        >>> r.push('l', 'aaa')
        'OK'
        >>> try:
        ...     r.lset('l', 1, 'a')
        ... except ResponseError, e:
        ...     print e
        index out of range
        >>> r.lset('l', 0, 'bbb')
        'OK'
        >>> r.lrange('l', 0, 1)
        ['bbb']
        >>> 
        """
        self.connect()
        try:
            value = value if isinstance(value, basestring) else str(value)
            self._write('LSET %s %s %s\r\n%s\r\n' % (
                name, index, len(value), value
            ))
        except UnicodeEncodeError, e:
            raise InvalidData("Error encoding unicode value for element %s in list '%s': %s." % (index, name, e))
        return self._get_simple_response()
    
    def sadd(self, name, value):
        """
        >>> r = Redis()
        >>> res = r.delete('s')
        >>> r.sadd('s', 'a')
        1
        >>> r.sadd('s', 'b')
        1
        >>> 
        """
        self.connect()
        # same considerations on unicode as in set() apply here
        try:
            value = value if isinstance(value, basestring) else str(value)
            self._write('SADD %s %s\r\n%s\r\n' % (
                name, len(value), value
            ))
        except UnicodeEncodeError, e:
            raise InvalidData("Error encoding unicode value for element in set '%s': %s." % (name, e))
        return self._get_numeric_response()
        
    def srem(self, name, value):
        """
        >>> r = Redis()
        >>> r.delete('s')
        1
        >>> r.srem('s', 'aaa')
        0
        >>> r.sadd('s', 'b')
        1
        >>> r.srem('s', 'b')
        1
        >>> r.sismember('s', 'b')
        0
        >>> 
        """
        self.connect()
        # same considerations on unicode as in set() apply here
        try:
            value = value if isinstance(value, basestring) else str(value)
            self._write('SREM %s %s\r\n%s\r\n' % (
                name, len(value), value
            ))
        except UnicodeEncodeError, e:
            raise InvalidData("Error encoding unicode value for element in set '%s': %s." % (name, e))
        return self._get_numeric_response()
    
    def sismember(self, name, value):
        """
        >>> r = Redis()
        >>> r.delete('s')
        1
        >>> r.sismember('s', 'b')
        0
        >>> r.sadd('s', 'a')
        1
        >>> r.sismember('s', 'b')
        0
        >>> r.sismember('s', 'a')
        1
        >>>
        """
        self.connect()
        # same considerations on unicode as in set() apply here
        try:
            value = value if isinstance(value, basestring) else str(value)
            self._write('SISMEMBER %s %s\r\n%s\r\n' % (
                name, len(value), value
            ))
        except UnicodeEncodeError, e:
            raise InvalidData("Error encoding unicode value for element in set '%s': %s." % (name, e))
        return self._get_numeric_response()
    
    def sinter(self, *args):
        """
        >>> r = Redis()
        >>> res = r.delete('s1')
        >>> res = r.delete('s2')
        >>> res = r.delete('s3')
        >>> r.sadd('s1', 'a')
        1
        >>> r.sadd('s2', 'a')
        1
        >>> r.sadd('s3', 'b')
        1
        >>> try:
        ...     r.sinter()
        ... except ResponseError, e:
        ...     print e
        wrong number of arguments
        >>> try:
        ...     r.sinter('l')
        ... except ResponseError, e:
        ...     print e
        ('LINTER against key not holding a set value', 42)
        >>> r.sinter('s1', 's2', 's3')
        []
        >>> r.sinter('s1', 's2')
        ['a']
        >>> 
        """
        self.connect()
        self._write('SINTER %s\r\n' % ' '.join(args))
        results = list()
        try:
            num = self._get_numeric_response(allow_negative=False)
        except InvalidResponse, e:
            if e.args[1] == 'nil':
                return results
            raise
        while num:
            results.append(self._get_value())
            num -= 1
        return results

    def smembers(self, name):
        """
        >>> r = Redis()
        >>> r.delete('s')
        1
        >>> r.sadd('s', 'a')
        1
        >>> r.sadd('s', 'b')
        1
        >>> try:
        ...     r.smembers('l')
        ... except ResponseError, e:
        ...     print e
        ('LINTER against key not holding a set value', 42)
        >>> r.smembers('s')
        ['a', 'b']
        >>> 
        """
        self.connect()
        self._write('SMEMBERS %s\r\n' % name)
        results = list()
        try:
            num = self._get_numeric_response(allow_negative=False)
        except InvalidResponse, e:
            if e.args[1] == 'nil':
                return results
            raise
        while num:
            results.append(self._get_value())
            num -= 1
        return results

    def select(self, db):
        """
        >>> r = Redis()
        >>> r.delete('a')
        1
        >>> r.select(1)
        'OK'
        >>> r.set('a', 1)
        'OK'
        >>> r.select(0)
        'OK'
        >>> r.get('a')
        >>> 
        """
        self.connect()
        self._write('SELECT %s\r\n' % db)
        return self._get_simple_response()
    
    def move(self, name, db):
        """
        >>> r = Redis()
        >>> r.select(0)
        'OK'
        >>> r.set('a', 'a')
        'OK'
        >>> r.select(1)
        'OK'
        >>> if r.get('a'):
        ...     r.delete('a')
        ... else:
        ...     print 1
        1
        >>> r.select(0)
        'OK'
        >>> r.move('a', 1)
        1
        >>> r.get('a')
        >>> r.select(1)
        'OK'
        >>> r.get('a')
        'a'
        >>> r.select(0)
        'OK'
        >>> 
        """
        self.connect()
        self._write('MOVE %s %s\r\n' % (name, db))
        return self._get_numeric_response()
    
    def save(self, background=False):
        """
        >>> r = Redis()
        >>> r.save()
        'OK'
        >>> try:
        ...     resp = r.save(background=True)
        ... except ResponseError, e:
        ...     assert str(e) == 'background save already in progress', str(e)
        ... else:
        ...     assert resp == 'OK'
        >>> 
        """
        self.connect()
        if background:
            self._write('BGSAVE\r\n')
        else:
            self._write('SAVE\r\n')
        return self._get_simple_response()
        
    def lastsave(self):
        """
        >>> import time
        >>> r = Redis()
        >>> t = int(time.time())
        >>> r.save()
        'OK'
        >>> r.lastsave() >= t
        True
        >>> 
        """
        self.connect()
        self._write('LASTSAVE\r\n')
        return self._get_numeric_response()
    
    def _get_value(self):
        data = self._read().strip()
        if data == 'nil':
            return
        elif data[0] == '-':
            self._check_for_error(data)
        try:
            l = int(data)
        except (TypeError, ValueError):
            raise ResponseError("Cannot parse response '%s' as data length." % data)
        buf = []
        while l > 0:
            data = self._read()
            l -= len(data)
            if len(data) > l:
                # we got the ending crlf
                data = data.strip()
            buf.append(data)
        if l == 0:
            # the data has a trailing crlf embedded, let's restore it
            buf.append(self._read())
        return ''.join(buf)
    
    def _get_simple_response(self):
        data = self._read().strip()
        if data[0] == '+':
            return data[1:]
        self._check_for_error(data)
        raise InvalidResponse("Cannot parse first line '%s' for a simple response." % data, data)

    def _get_numeric_response(self, allow_negative=True):
        data = self._read().strip()
        try:
            value = int(data)
        except (TypeError, ValueError), e:
            pass
        else:
            if not allow_negative and value < 0:
                self._check_for_error(data)
            return value
        self._check_for_error(data)
        raise InvalidResponse("Cannot parse first line '%s' for a numeric response: %s." % (data, e), data)
        
    def _check_for_error(self, data):
        if not data or data[0] != '-':
            return
        if data.startswith('-ERR '):
            raise ResponseError(data[5:])
        try:
            error_code = int(data[1:])
        except (TypeError, ValueError):
            raise ResponseError("Unknown error format '%s'." % data)
        error_message = self._read().strip()
        raise ResponseError(error_message, error_code)
        
    def disconnect(self):
        if isinstance(self._sock, socket.socket):
            try:
                self._sock.close()
            except socket.error:
                pass
        self._sock = None
        self._fp = None
            
    def connect(self):
        """
        >>> r = Redis()
        >>> r.connect()
        >>> isinstance(r._sock, socket.socket)
        True
        >>> 
        """
        if isinstance(self._sock, socket.socket):
            return
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.host, self.port))
        except socket.error, e:
            raise ConnectionError("Error %s connecting to %s:%s. %s." % (e.args[0], self.host, self.port, e.args[1]))
        else:
            self._sock = sock
            self._fp = self._sock.makefile('r')
        
            
if __name__ == '__main__':
    import doctest
    doctest.testmod()
    