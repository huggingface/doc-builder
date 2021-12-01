from argparse import ArgumentParser

from doc_builder.commands.build import build_command_parser
from doc_builder.commands.convert_doc_file import convert_command_parser


def main():
    parser = ArgumentParser("Doc Builder CLI tool", usage="doc-builder <command> [<args>]")
    subparsers = parser.add_subparsers(help="doc-builder command helpers")

    # Register commands
    convert_command_parser(subparsers=subparsers)
    build_command_parser(subparsers=subparsers)

    # Let's go
    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        exit(1)

    # Run
    args.func(args)


if __name__ == "__main__":
    main()