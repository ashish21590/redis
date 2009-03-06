<?php
/*******************************************************************************
 * Redis PHP Bindings - http://code.google.com/p/redis/
 *
 * Copyright 2009 Ludovico Magnocavallo
 * Released under the same license as Redis.
 *
 * $Revision$
 * $Date$
 ******************************************************************************/


class Redis {
    
    var $server;
    var $port;
    var $_sock;
 
    function Redis($host, $port=6379) {
        $this->host = $host;
        $this->port = $port;
    }
    
    function connect() {
        if ($this->_sock)
            return;
        if ($sock = fsockopen($this->host, $this->port, $errno, $errstr)) {
            $this->_sock = $sock;
            return;
        }
        $msg = "Cannot open socket to {$this->host}:{$this->port}";
        if ($errno || $errmsg)
            $msg .= "," . ($errno ? " error $errno" : "") . ($errmsg ? " $errmsg" : "");
        trigger_error("$msg.", E_USER_ERROR);
    }
    
    function disconnect() {
        if ($this->_sock)
            @fclose($this->_sock);
        $this->_sock = null;
    }
    
    function &_write($s) {
        while ($s) {
            $i = fwrite($this->_sock, $s);
            if ($i == 0)
                break;
            $s = substr($s, $i);
        }
    }
    
    function &_read($len=1024) {
        if ($s = fgets($this->_sock))
            return $s;
        $this->disconnect();
        trigger_error("Cannot read from socket.", E_USER_ERROR);
    }
    
    function &ping() {
        $this->connect();
        $this->_write("PING\r\n");
        return $this->_simple_response();
    }
    
    function &_simple_response() {
        $s =& $this->_read();
        if ($s[0] == '+')
            return substr($s, 1);
        if ($err =& $this->_check_for_error())
            return $err;
        trigger_error("Cannot parse first line '$s' for a simple response", E_USER_ERROR);
    }
    
}   

$r =& new Redis('localhost');
$r->connect();
echo $r->ping();

?>