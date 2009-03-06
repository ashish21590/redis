<?php
/*******************************************************************************
 * Redis PHP Bindings - http://code.google.com/p/redis/
 *
 * Copyright 2009 Ludovico Magnocavallo
 * Released under the same license as Redis.
 *
 * Version: 0.1
 *
 * $Revision$
 * $Date$
 *
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
    
    function &ping() {
        $this->connect();
        $this->_write("PING\r\n");
        return $this->_simple_response();
    }
    
    function &do_echo($s) {
        $this->connect();
        $this->_write("ECHO " . strlen($s) . "\r\n$s\r\n");
        return $this->_get_value();
    }
    
    function &set($name, $value, $preserve=false) {
        $this->connect();
        $this->_write(
            ($preserve ? 'SETNX' : 'SET') .
            " $name " . strlen($value) . "\r\n$value\r\n"
        );
        return $preserve ? $this->_numeric_response() : $this->_simple_response();
    }
    
    function &get($name) {
        $this->connect();
        $this->_write("GET $name\r\n");
        return $this->_get_value();
    }
    
    function &incr($name, $amount=1) {
        $this->connect();
        if ($amount == 1)
            $this->_write("INCR $name\r\n");
        else
            $this->_write("INCRBY $name $amount\r\n");
        return $this->_numeric_response();
    }
    
    function &decr($name, $amount=1) {
        $this->connect();
        if ($amount == 1)
            $this->_write("DECR $name\r\n");
        else
            $this->_write("DECRBY $name $amount\r\n");
        return $this->_numeric_response();
    }
    
    function &exists($name) {
        $this->connect();
        $this->_write("EXISTS $name\r\n");
        return $this->_numeric_response();
    }
    
    function &delete($name) {
        $this->connect();
        $this->_write("DEL $name\r\n");
        return $this->_numeric_response();
    }
    
    function &keys($pattern) {
        $this->connect();
        $this->_write("KEYS $pattern\r\n");
        return explode(' ', $this->_get_value());
    }
    
    function &randomkey() {
        $this->connect();
        $this->_write("RANDOMKEY\r\n");
        $s =& trim($this->_read());
        $this->_check_for_error($s);
        return $s;
    }
    
    function &rename($src, $dst, $preserve=False) {
        $this->connect();
        if ($preserve) {
            $this->_write("RENAMENX $src $dst\r\n");
            return $this->_numeric_response();
        }
        $this->_write("RENAME $src $dst\r\n");
        return trim($this->_simple_response());
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
    
    function _check_for_error(&$s) {
        if (!$s || $s[0] != '-')
            return;
        if (substr($s, 0, 4) == '-ERR')
            trigger_error("Redis error: " . trim(substr($s, 4)), E_USER_ERROR);
        trigger_error("Redis error: " . substr(trim($this->_read()), 5), E_USER_ERROR);
    }
    
    function &_simple_response() {
        $s =& trim($this->_read());
        if ($s[0] == '+')
            return substr($s, 1);
        if ($err =& $this->_check_for_error($s))
            return $err;
        trigger_error("Cannot parse first line '$s' for a simple response", E_USER_ERROR);
    }
    
    function &_numeric_response($allow_negative=True) {
        $s =& trim($this->_read());
        $i = (int)$s;
        if ($i . '' == $s) {
            if (!$allow_negative && $i < 0)
                $this->_check_for_error($s);
            return $i;
        }
        trigger_error("Cannot parse '$s' as numeric response.");
    }
    
    function &_get_value() {
        $s =& trim($this->_read());
        if ($s == 'nil')
            return '';
        else if ($s[0] == '-')
            $this->_check_for_error($s);
        $i = (int)$s;
        if ($i . '' != $s)
            trigger_error("Cannot parse '$s' as data length.");
        $buffer = '';
        while ($i > 0) {
            $s = $this->_read();
            $l = strlen($s);
            $i -= $l;
            if ($l > $i) // ending crlf
                $s = rtrim($s);
            $buffer .= $s;
        }
        if ($i == 0)    // let's restore the trailing crlf
            $buffer .= $this->_read();
        return $buffer;
    }
    
}   

$r =& new Redis('localhost');
$r->connect();
echo $r->ping() . "\n";
echo $r->do_echo('ECHO test') . "\n";
echo "SET aaa " . $r->set('aaa', 'bbb') . "\n";
echo "SETNX aaa " . $r->set('aaa', 'ccc', true) . "\n";
echo "GET aaa " . $r->get('aaa') . "\n";
echo "INCR aaa " . $r->incr('aaa') . "\n";
echo "GET aaa " . $r->get('aaa') . "\n";
echo "INCRBY aaa 3 " . $r->incr('aaa', 2) . "\n";
echo "GET aaa " . $r->get('aaa') . "\n";
echo "DECR aaa " . $r->decr('aaa') . "\n";
echo "GET aaa " . $r->get('aaa') . "\n";
echo "DECRBY aaa 2 " . $r->decr('aaa', 2) . "\n";
echo "GET aaa " . $r->get('aaa') . "\n";
echo "EXISTS aaa " . $r->exists('aaa') . "\n";
echo "EXISTS fsfjslfjkls " . $r->exists('fsfjslfjkls') . "\n";
echo "DELETE aaa " . $r->delete('aaa') . "\n";
echo "EXISTS aaa " . $r->exists('aaa') . "\n";
echo 'SET a1 a2 a3' . $r->set('a1', 'a') . $r->set('a2', 'b') . $r->set('a3', 'c') . "\n";
echo 'KEYS a* ' . print_r($r->keys('a*'), true) . "\n";
echo 'RANDOMKEY ' . $r->randomkey('a*') . "\n";
echo 'RENAME a1 a0 ' . $r->rename('a1', 'a0') . "\n";
echo 'RENAMENX a0 a2 ' . $r->rename('a0', 'a2', true) . "\n";
echo 'RENAMENX a0 a1 ' . $r->rename('a0', 'a1', true) . "\n";

?>