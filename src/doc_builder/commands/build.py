import argparse
import importlib
from doc_builder import build_doc, update_versions_file


def build_command(args):
    if args.version is None:
        module = importlib.import_module(args.library_name)
        version = module.__version__

        if "dev" in version:
            version = "master"
        else:
            version = f"v{version}"
    else:
        version = args.version

    output_path = f"./build/{args.library_name}/{version}/{args.language}"

    print("Building docs for", args.library_name, args.path_to_docs, output_path)
    build_doc(args.library_name, args.path_to_docs, output_path)
    update_versions_file(f"./build/{args.library_name}", version)


def build_command_parser(subparsers=None):
    if subparsers is not None:
        parser = subparsers.add_parser("build")
    else:
        parser = argparse.ArgumentParser("Doc Builder build command")

    parser.add_argument("library_name", type=str, help="Library name")
    parser.add_argument(
        "path_to_docs",
        type=str,
        help="Local path to library documentation. The library should be cloned, and the folder containing the "
             "documentation files should be indicated here."
    )
    parser.add_argument("--language", type=str, help="Language of the documentation to generate", default="en")
    parser.add_argument(
        "--version",
        type=str,
        help="Version under which to push the files. Will not affect the actual files generated, as these are"
             " generated according to the `path_to_docs` argument.",
    )

    if subparsers is not None:
        parser.set_defaults(func=build_command)
    return parser
