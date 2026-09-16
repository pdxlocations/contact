import unittest

from contact.utilities.arg_parser import __version__, setup_parser


class ArgParserTests(unittest.TestCase):
    def test_demo_screenshot_flag_is_supported(self) -> None:
        args = setup_parser().parse_args(["--demo-screenshot"])
        self.assertTrue(args.demo_screenshot)

    def test_demo_screenshot_defaults_to_false(self) -> None:
        args = setup_parser().parse_args([])
        self.assertFalse(args.demo_screenshot)

    def test_version_flag_exits_zero(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            setup_parser().parse_args(["--version"])
        self.assertEqual(ctx.exception.code, 0)

    def test_version_short_flag_exits_zero(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            setup_parser().parse_args(["-V"])
        self.assertEqual(ctx.exception.code, 0)

    def test_version_is_not_none(self) -> None:
        self.assertIsNotNone(__version__)
