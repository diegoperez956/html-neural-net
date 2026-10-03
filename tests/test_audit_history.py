import unittest

from scripts.audit_history import inspect


class HistoryInventoryTests(unittest.TestCase):
    def test_records_scripts_handlers_and_urls(self):
        result = inspect('<script>draw()</script><div onclick="f()"></div>'
                         '<style>@import "https://example.invalid/model.css";</style>')
        self.assertEqual(result["scripts"], ["draw()"])
        self.assertEqual(result["inline_handlers"], ["onclick"])
        self.assertEqual(result["network_urls"], ["https://example.invalid/model.css"])

    def test_flags_complete_input_selector_after_embedded_font(self):
        font = "A" * 200_000
        result = inspect('<style>@font-face { src: url(data:font/woff2;base64,' + font + '); }'
                         '#netbus:has(#a:checked):has(#b:checked) { --result: 1; }</style>')
        self.assertEqual(result["rules_with_multiple_has_selectors"], 1)

    def test_single_input_mappings_are_not_lookup_rows(self):
        result = inspect('<style>@property --a { syntax: "<integer>"; inherits: true; initial-value: 0; }'
                         'body.rt:has(#a:checked) { --a: 1; }'
                         'body.rt:has(#b:checked) { --b: 1; }</style>')
        self.assertEqual(result["registered_signals"], 1)
        self.assertEqual(result["rules_with_multiple_has_selectors"], 0)
        self.assertEqual(result["scripts"], [])
