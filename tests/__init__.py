import tempfile
import slmkiii
import unittest
import slmkiii.template.sections as sections


class TestTemplate(unittest.TestCase):
    def assert_equal_templates(self, template1, template2):
        json1 = template1.export_json()
        json2 = template2.export_json()
        self.assertEqual(json1['name'], json2['name'])
        self.assertEqual(json1['version'], json2['version'])
        for sdata in sections:
            section = sdata['name']
            self.assertListEqual(json1[section], json2[section])
        json1 = template1.export_json(minify=True)
        json2 = template2.export_json(minify=True)
        self.assertEqual(json1['name'], json2['name'])
        self.assertEqual(json1['version'], json2['version'])
        for sdata in sections:
            section = sdata['name']
            self.assertListEqual(json1[section], json2[section])

    def test_parse_sysex_and_json_export(self):
        template1 = slmkiii.Template('tests/data/expected_1.json')
        template2 = slmkiii.Template('tests/data/test1.syx')
        self.assertDictEqual(template1.export_json(), template2.export_json())

    def test_parse_seven_bit_raw_and_json_export(self):
        with open('tests/data/test1.syx', 'rb') as r:
            raw = r.read()
        template1 = slmkiii.Template('tests/data/expected_1.json')
        template2 = slmkiii.Template(raw)
        self.assertDictEqual(template1.export_json(), template2.export_json())

    def test_parse_eight_bit_raw(self):
        with open('tests/data/test1.syx', 'rb') as r:
            raw = r.read()
        template1 = slmkiii.Template(raw)
        template2 = slmkiii.Template(template1._data)
        self.assertDictEqual(template1.export_json(), template2.export_json())

    def test_parse_invalid_sysex(self):
        with open('tests/data/test1.syx', 'rb') as r:
            raw = r.read()
        raw += b'uh oh'
        with self.assertRaises(slmkiii.errors.ErrorUnknownData):
            slmkiii.Template(raw)
        with self.assertRaises(slmkiii.errors.ErrorUnknownData):
            slmkiii.Template('wut')

    def test_sysex_export_sysex(self):
        template1 = slmkiii.Template('tests/data/expected_1.json')
        with open('tests/data/expected_1.syx', 'rb') as f:
            sysex = f.read()
        self.assertEqual(sysex, template1.export_sysex())

    def test_save_export_json(self):
        tf = tempfile.NamedTemporaryFile(suffix='.syx')
        template1 = slmkiii.Template('tests/data/expected_1.json')
        template1.save(tf.name)
        template2 = slmkiii.Template(tf.name)
        with open('tests/data/expected_1.syx', 'rb') as f:
            sysex2 = f.read()
        self.assertEqual(template2.export_sysex(), sysex2)

    def test_save_json(self):
        tf = tempfile.NamedTemporaryFile(suffix='.json')
        template1 = slmkiii.Template('tests/data/test1.syx')
        template1.save(tf.name)
        template2 = slmkiii.Template(tf.name)
        self.assertDictEqual(template1.export_json(), template2.export_json())

    def test_save_export_sysex(self):
        tf = tempfile.NamedTemporaryFile(suffix='.syx')
        template1 = slmkiii.Template('tests/data/expected_1.json')
        template1.save(tf.name)
        with open(tf.name, 'rb') as f:
            sysex1 = f.read()
        with open('tests/data/expected_1.syx', 'rb') as f:
            sysex2 = f.read()
        self.assertEqual(sysex1, sysex2)

    def test_default_json(self):
        template1 = slmkiii.Template('tests/data/minimal_1.json')
        template2 = slmkiii.Template('tests/data/expected_2.json')
        self.assertDictEqual(template1.export_json(), template2.export_json())
        self.assertEqual(template1.knobs[0].message_type_name, 'CC')
        self.assertEqual(template1.knobs[0].short_message_type_name, 'CC')

    def test_invalid_extension(self):
        tf = tempfile.NamedTemporaryFile(suffix='.fail')
        with self.assertRaises(slmkiii.errors.ErrorUnknownExtension):
            slmkiii.Template(tf.name)

    def test_bad_import(self):
        with self.assertRaises(slmkiii.errors.ErrorTooManyItemsInSection):
            slmkiii.Template('tests/data/expected_bad_1.json')

    def test_minify_json(self):
        template1 = slmkiii.Template('tests/data/minimal_2.json')
        template2 = slmkiii.Template('tests/data/test2.syx')
        self.assert_equal_templates(template1, template2)

    def test_bad_json_version(self):
        with self.assertRaises(slmkiii.errors.ErrorUnknownVersion):
            slmkiii.Template('tests/data/bad_version.json')

    def test_bad_checksum(self):
        with self.assertRaises(slmkiii.errors.ErrorInvalidChecksum):
            slmkiii.Template('tests/data/bad_checksum.syx')

    def test_do_not_replace(self):
        tf = tempfile.NamedTemporaryFile(suffix='.syx')
        template = slmkiii.Template('tests/data/minimal_2.json')
        template.save(tf.name)
        with self.assertRaises(slmkiii.errors.ErrorFileExists):
            template.save(tf.name, overwrite=False)

    def test_create_new(self):
        tf = tempfile.NamedTemporaryFile(suffix='.syx')
        template1 = slmkiii.Template()
        template1.save(tf.name)
        template2 = slmkiii.Template(tf.name)
        self.assert_equal_templates(template1, template2)

    def test_attribute_modification_roundtrip(self):
        template = slmkiii.Template()
        template.name = 'Modified'
        template.buttons[0].name = 'MyButton'
        template.buttons[0].channel = 5
        template.buttons[0].message_type = 2
        template.buttons[0].fourth_param = 42
        template.knobs[0].name = 'MyKnob'
        template.knobs[0].channel = 10
        template.knobs[0].message_type = 1
        template.knobs[0].first_param = 99
        template.faders[0].name = 'MyFader'
        template.faders[0].channel = 3
        template.faders[0].message_type = 0
        template.faders[0].second_param = 77

        tf = tempfile.NamedTemporaryFile(suffix='.syx', delete=False)
        template.save(tf.name)
        reloaded = slmkiii.Template(tf.name)

        self.assertEqual(reloaded.name, 'Modified')
        self.assertEqual(reloaded.buttons[0].name, 'MyButton')
        self.assertEqual(reloaded.buttons[0].channel, 5)
        self.assertEqual(reloaded.buttons[0].message_type, 2)
        self.assertEqual(reloaded.buttons[0].fourth_param, 42)
        self.assertEqual(reloaded.knobs[0].name, 'MyKnob')
        self.assertEqual(reloaded.knobs[0].channel, 10)
        self.assertEqual(reloaded.knobs[0].message_type, 1)
        self.assertEqual(reloaded.knobs[0].first_param, 99)
        self.assertEqual(reloaded.faders[0].name, 'MyFader')
        self.assertEqual(reloaded.faders[0].channel, 3)
        self.assertEqual(reloaded.faders[0].message_type, 0)
        self.assertEqual(reloaded.faders[0].second_param, 77)

    def test_channel_roundtrip(self):
        for channel_value in [1, 8, 16, 'default']:
            template = slmkiii.Template()
            template.buttons[0].channel = channel_value
            template.knobs[0].channel = channel_value
            template.faders[0].channel = channel_value
            template.pad_hits[0].channel = channel_value

            tf = tempfile.NamedTemporaryFile(suffix='.syx', delete=False)
            template.save(tf.name)
            reloaded = slmkiii.Template(tf.name)

            self.assertEqual(reloaded.buttons[0].channel, channel_value,
                             f"Button channel {channel_value} did not round-trip")
            self.assertEqual(reloaded.knobs[0].channel, channel_value,
                             f"Knob channel {channel_value} did not round-trip")
            self.assertEqual(reloaded.faders[0].channel, channel_value,
                             f"Fader channel {channel_value} did not round-trip")
            self.assertEqual(reloaded.pad_hits[0].channel, channel_value,
                             f"PadHit channel {channel_value} did not round-trip")

    def test_name_truncation(self):
        template = slmkiii.Template()
        template.knobs[0].name = 'VeryLongNameThatExceeds9'
        tf = tempfile.NamedTemporaryFile(suffix='.syx', delete=False)
        template.save(tf.name)
        reloaded = slmkiii.Template(tf.name)
        self.assertTrue(len(reloaded.knobs[0].name) <= 9)

    def test_message_type_name_setter(self):
        template = slmkiii.Template()
        knob = template.knobs[0]
        for name, expected_type in [
            ('CC', 0), ('NRPN', 1), ('Note', 2),
            ('Program Change', 3), ('Song Position', 4),
            ('Channel Pressure', 5), ('Poly Aftertouch', 6),
        ]:
            knob.message_type_name = name
            self.assertEqual(knob.message_type, expected_type)
            self.assertEqual(knob.message_type_name, name)
