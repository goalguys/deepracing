# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: TimestampedPacketCarTelemetryData.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import PacketCarTelemetryData_pb2 as PacketCarTelemetryData__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='TimestampedPacketCarTelemetryData.proto',
  package='deepf1.twenty_eighteen.protobuf',
  syntax='proto3',
  serialized_options=None,
  serialized_pb=_b('\n\'TimestampedPacketCarTelemetryData.proto\x12\x1f\x64\x65\x65pf1.twenty_eighteen.protobuf\x1a\x1cPacketCarTelemetryData.proto\"\x83\x01\n!TimestampedPacketCarTelemetryData\x12K\n\nudp_packet\x18\x01 \x01(\x0b\x32\x37.deepf1.twenty_eighteen.protobuf.PacketCarTelemetryData\x12\x11\n\ttimestamp\x18\x02 \x01(\x04\x62\x06proto3')
  ,
  dependencies=[PacketCarTelemetryData__pb2.DESCRIPTOR,])




_TIMESTAMPEDPACKETCARTELEMETRYDATA = _descriptor.Descriptor(
  name='TimestampedPacketCarTelemetryData',
  full_name='deepf1.twenty_eighteen.protobuf.TimestampedPacketCarTelemetryData',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='udp_packet', full_name='deepf1.twenty_eighteen.protobuf.TimestampedPacketCarTelemetryData.udp_packet', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='timestamp', full_name='deepf1.twenty_eighteen.protobuf.TimestampedPacketCarTelemetryData.timestamp', index=1,
      number=2, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=107,
  serialized_end=238,
)

_TIMESTAMPEDPACKETCARTELEMETRYDATA.fields_by_name['udp_packet'].message_type = PacketCarTelemetryData__pb2._PACKETCARTELEMETRYDATA
DESCRIPTOR.message_types_by_name['TimestampedPacketCarTelemetryData'] = _TIMESTAMPEDPACKETCARTELEMETRYDATA
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

TimestampedPacketCarTelemetryData = _reflection.GeneratedProtocolMessageType('TimestampedPacketCarTelemetryData', (_message.Message,), {
  'DESCRIPTOR' : _TIMESTAMPEDPACKETCARTELEMETRYDATA,
  '__module__' : 'TimestampedPacketCarTelemetryData_pb2'
  # @@protoc_insertion_point(class_scope:deepf1.twenty_eighteen.protobuf.TimestampedPacketCarTelemetryData)
  })
_sym_db.RegisterMessage(TimestampedPacketCarTelemetryData)


# @@protoc_insertion_point(module_scope)
