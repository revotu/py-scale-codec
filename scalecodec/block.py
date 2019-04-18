#  Scale Codec
#  Copyright (C) 2019  openAware B.V.
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

from collections import OrderedDict

from scalecodec.base import ScaleDecoder
from scalecodec.metadata import MetadataDecoder
from scalecodec.types import Vec


class ExtrinsicsDecoder(ScaleDecoder):
    type_mapping = (
        ('extrinsic_length', 'Compact<u32>'),
        ('version_info', 'u8'),
        ('address', 'Address'),
        ('signature', 'Signature'),
        ('nonce', 'Compact<u32>'),
        ('era', 'Era'),
        ('call_index', '(u8,u8)'),
    )

    def __init__(self, data, sub_type=None, metadata: MetadataDecoder = None):

        assert (type(metadata) == MetadataDecoder)

        self.metadata = metadata
        self.extrinsic_length = None
        self.version_info = None
        self.contains_transaction: bool = False
        self.address = None
        self.signature = None
        self.nonce = None
        self.era = None
        self.call_index = None
        self.call_module = None
        self.call = None
        self.call_args = None
        self.params = []
        super().__init__(data, sub_type)

    def process(self):
        # TODO for all attributes
        attribute_types = OrderedDict(self.type_mapping)

        self.extrinsic_length = self.process_type('Compact<u32>').value

        if self.extrinsic_length != self.data.get_remaining_length():
            # Fallback for legacy version
            self.extrinsic_length = None
            self.data.reset()

        self.version_info = self.get_next_bytes(1).hex()

        self.contains_transaction = int(self.version_info, 16) >= 80

        if self.contains_transaction:
            self.address = self.process_type('Address')

            self.signature = self.process_type('Signature')

            self.nonce = self.process_type(attribute_types['nonce'])

            self.era = self.process_type('Era')

        self.call_index = self.get_next_bytes(2).hex()

        if self.call_index:

            # Decode params

            self.call = self.metadata.call_index[self.call_index][1]
            self.call_module = self.metadata.call_index[self.call_index][0]

            for arg in self.call.args:
                arg_type_obj = self.process_type(arg.type, metadata=self.metadata)

                self.params.append({
                    'name': arg.name,
                    'type': arg.type,
                    'value': arg_type_obj.serialize(),
                    'valueRaw': arg_type_obj.raw_value
                })

        result = {
            'valueRaw': self.raw_value,
            'extrinsic_length': self.extrinsic_length,
            'version_info': self.version_info,
        }

        if self.contains_transaction:
            result['account_length'] = self.address.account_length
            result['account_id'] = self.address.account_id
            result['account_index'] = self.address.account_index
            result['signature'] = self.signature.value
            result['nonce'] = self.nonce.value
            result['era'] = self.era.value
        if self.call_index:
            result['call_code'] = self.call_index
            result['call_module_function'] = self.call.get_identifier()
            result['call_module'] = self.call_module.get_identifier()

        result['params'] = self.params

        return result


class ExtrinsicsBlock61181Decoder(ExtrinsicsDecoder):
    type_mapping = (
        ('extrinsic_length', 'Compact<u32>'),
        ('version_info', 'u8'),
        ('address', 'Address'),
        ('signature', 'Signature'),
        ('nonce', 'u64'),
        ('era', 'Era'),
        ('call_index', '(u8,u8)'),
    )


class EventsDecoder(Vec):
    type_string = 'Vec<EventRecord>'

    def __init__(self, data, metadata=None, **kwargs):
        assert (type(metadata) == MetadataDecoder)

        self.metadata = metadata
        self.elements = []

        super().__init__(data, metadata=metadata, **kwargs)

    def process(self):
        element_count = self.process_type('Compact<u32>').value

        for i in range(0, element_count):
            element = self.process_type('EventRecord', metadata=self.metadata)
            element.value['event_idx'] = i
            self.elements.append(element)

        return [e.value for e in self.elements]


class EventRecord(ScaleDecoder):

    def __init__(self, data, sub_type=None, metadata: MetadataDecoder = None):

        assert (type(metadata) == MetadataDecoder)

        self.metadata = metadata

        self.phase = None
        self.extrinsic_idx = None
        self.type = None
        self.params = []
        self.event = None
        self.event_module = None

        super().__init__(data, sub_type)

    def process(self):

        # TODO Create option type
        self.phase = self.get_next_u8()

        if self.phase == 0:
            self.extrinsic_idx = self.process_type('U32').value

        self.type = self.get_next_bytes(2).hex()

        # Decode params

        self.event = self.metadata.event_index[self.type][1]
        self.event_module = self.metadata.event_index[self.type][0]

        for arg_type in self.event.args:
            arg_type_obj = self.process_type(arg_type)

            self.params.append({
                'type': arg_type,
                'value': arg_type_obj.serialize(),
                'valueRaw': arg_type_obj.raw_value
            })

        return {
            'phase': self.phase,
            'extrinsic_idx': self.extrinsic_idx,
            'type': self.type,
            'module_id': self.event_module.name,
            'event_id': self.event.name,
            'params': self.params
        }