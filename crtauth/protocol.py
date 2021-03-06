# Copyright (c) 2011-2013 Spotify AB
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

from crtauth.exceptions import InvalidInputException


class Field(object):
    """
    Base class for definining a static field type.
    """

    def pack(self, packing, packer, value):
        """
        Pack a value using the specified packer.

        :param packing: Packing method to use.
        :param packer: Active packer to append value to.
        :param value: Value to pack.
        """
        raise NotImplementedError("pack")

    def unpack(self, packing, unpacker):
        """
        Unpack a value using the specified unpacker.

        :param packing: Packing method to use.
        :param unpacker: Active unpacker to extract value from.
        """
        raise NotImplementedError("unpack")


class FString(Field):
    """
    Fixed length string type.
    """
    def __init__(self, size):
        self.size = size

    def pack(self, packing, packer, value):
        return packer.pack_fstring(self.size, value)

    def unpack(self, packing, unpacker):
        return unpacker.unpack_fstring(self.size)


class String(Field):
    """
    Variable length string type.
    """
    def pack(self, packing, packer, value):
        return packer.pack_string(value)

    def unpack(self, packing, unpacker):
        return unpacker.unpack_string()


class UInt(Field):
    """
    Unsigned integer.
    """
    def pack(self, packing, packer, value):
        return packer.pack_uint(value)

    def unpack(self, packing, unpacker):
        return unpacker.unpack_uint()


class Type(Field):
    """
    Encapsulate other type.
    """
    def __init__(self, cls):
        self.cls = cls

    def pack(self, packing, packer, value):
        return packer.pack_string(value.serialize(packing))

    def unpack(self, packing, unpacker):
        return self.cls.deserialize(packing, unpacker.unpack_string())


class SerializablePacket(object):
    __magic__ = None
    __fields__ = None

    def __init__(self, **kw):
        if len(kw) != len(self.__fields__):
            raise RuntimeError("Field length mismatch")

        for key, _ in self.__fields__:
            val = kw.get(key, None)
            if val is None:
                raise RuntimeError("Missing required argument '" + key + "'")
            setattr(self, key, val)

    def serialize(self, packing):
        if self.__magic__ is None or self.__fields__ is None:
            raise RuntimeError(
                "Serialization can only be performed on classes implementing "
                "__fields__ and __magic__")

        p = packing.Packer()

        p.pack_fstring(1, self.__magic__)

        for name, field in self.__fields__:
            value = getattr(self, name)
            field.pack(packing, p, value)

        return p.get_buffer()

    @classmethod
    def deserialize(cls, packing, buf):
        if cls.__magic__ is None or cls.__fields__ is None:
            raise RuntimeError(
                "Deserialization can only be performed on classes "
                "implementing __fields__ and __magic__")

        u = packing.Unpacker(buf)

        if u.unpack_fstring(1) != cls.__magic__:
            raise InvalidInputException(
                "Wrong magic byte for " + cls.__name__ +
                " (should be '" + hex(ord(cls.__magic__)) + "')")

        kw = dict()

        for name, field in cls.__fields__:
            kw[name] = field.unpack(packing, u)

        return cls(**kw)


class VerifiablePayload(SerializablePacket):
    """
    A digest and payload combination.

    digest - The payload digest.
    payload - The payload.
    """

    __magic__ = 'v'

    __fields__ = [
        ("digest", FString(20)),
        ("payload", String()),
    ]

    def verify(self, digest_f):
        return self.digest == digest_f(self.payload)


class Challenge(SerializablePacket):
    """
    Represents a challenge, with binary serialization support
    """

    __magic__ = 'c'

    __fields__ = [
        ("unique_data", FString(20)),
        ("valid_from", UInt()),
        ("valid_to", UInt()),
        ("fingerprint", String()),
        ("server_name", String()),
        ("username", String()),
    ]


class Response(SerializablePacket):
    """
    Represents a response to a challenge.

    signature - A signature generated by the client.
    hmac_challenge - A verifiable packed challenge (see VerifiablePayload).
    """
    __magic__ = 'r'

    __fields__ = [
        ("signature", String()),
        ("hmac_challenge", Type(VerifiablePayload))
    ]


class Token(SerializablePacket):
    """
    A token which verifies that can be used to authorize a specific user.
    """
    __magic__ = 't'

    __fields__ = [
        ("valid_from", UInt()),
        ("valid_to", UInt()),
        ("username", String()),
    ]
