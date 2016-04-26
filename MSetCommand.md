= MSET _key1_ _value1_ _key2_ _value2_ ... _keyN_ _valueN_ (Redis >= 1.1) =
# MSETNX _key1_ _value1_ _key2_ _value2_ ... _keyN_ _valueN_ (Redis >= 1.1) #
_Time complexity: O(1) to set every key_

> Set the the rispective keys to the rispective values. MSET will replace old
> values with new values, while MSETNX will not perform any operation at all
> even if just a single key already exists.

> Because of this semantic MSETNX can be used in order to set different keys
> representing different fields of an unique logic object in a way that
> ensures that either all the fields or none at all are set.

> Both MSET and MSETNX are atomic operations. This means that for instance
> if the keys A and B are modified, another client talking to Redis can either
> see the changes to both A and B at once, or no modification at all.

## MSET Return value ##

[Status code reply](ReplyTypes.md) Basically +OK as MSET can't fail

## MSETNX Return value ##

[Integer reply](ReplyTypes.md), specifically:

```
1 if the all the keys were set
0 if no key was set (at least one key already existed)
```

## See also ##

  * [MGET](MgetCommand.md)