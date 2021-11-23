import argparse
import importlib
from doc_builder import build_doc

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("library_name", type=str, help="Library name")
    parser.add_argument(
        "path_to_docs",
        type=str,
        help="Local path to library documentation. The library should be cloned, and the folder containing the "
             "documentation files should be indicated here."
    )
    parser.add_argument("--language", type=str, help="Language of the documentation to generate", default="en")

    args = parser.parse_args()

    module = importlib.import_module(args.library_name)
    version = module.__version__

    output_path = f"../build/{args.library_name}/v{version}/{args.language}"

    print("Building docs for", args.library_name, args.path_to_docs, output_path)
    build_doc(args.library_name, args.path_to_docs, output_path)
