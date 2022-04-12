# doc-builder

This is the package we use to build the documentation of our Hugging Face repos.

## Installation

You can install from PyPi with

```bash
pip install hf-doc-builder
```

To install from source, clone this repository then

```bash
cd doc-builder
pip install -e .
```

## Previewing

To preview the docs, use the following command:

```bash
doc-builder preview {package_name} {path_to_docs}
```

For example:
```bash
doc-builder preview datasets ~/Desktop/datasets/docs/source/
```

## Doc building

To build the documentation of a given package, use the following command:

```bash
doc-builder build {package_name} {path_to_docs} --build_dir {build_dir}
```

For instance, here is how you can build the Datasets documentation (requires `pip install datasets[dev]`) if you have cloned the repo in `~/git/datasets`:

```bash
doc-builder datasets ~/git/datasets/docs/source --build_dir ~/tmp/test-build
```

This will generate MDX files that you can preview like any Markdown file in your favorite editor. To have a look at the documentation in HTML, you need to install node version 14 or higher. Then you can run (still with the example on Datasets)

```bash
doc-builder datasets ~/git/datasets/docs/source --build_dir ~/tmp/test-build --html
```
which will build HTML files in `~/tmp/test-build`. You can then inspect those files in your browser.

`doc-builder` can also automatically convert some of the documentation guides or tutorials into notebooks. This requires two steps:
- add `[[open-in-colab]]` in the tutorial for which you want to build a notebook
- add `--notebook_dir {path_to_notebook_folder}` to the build command.

## Templates for GitHub Actions

`doc-builder` provides templates for GitHub Actions, so you can build your documentation with every pull request, push to some branch etc. To use them in your project, simply create the following three files in the `.github/workflows/` directory:

* `build_main_documentation.yml`: responsible for building the docs for the `main` branch, releases etc.
* `build_pr_documentation.yml`: responsible for building the docs on each PR
* `delete_doc_comment.yml`: responsible for removing the comments from the `HuggingFaceDocBuilderDev` bot that provides a URL to the PR docs.

Within each workflow, the main thing to include is a pointer from the `uses` field to the corresponding workflow in `doc-builder`. For example, this is what the PR workflow looks like in the `datasets` library:

```yaml
name: Build PR Documentation

on:
  pull_request:

concurrency:
  group: ${{ github.workflow }}-${{ github.head_ref || github.run_id }}
  cancel-in-progress: true

jobs:
  build:
    uses: huggingface/doc-builder/.github/workflows/build_pr_documentation.yml@main # Runs this doc-builder workflow
    with:
      commit_sha: ${{ github.event.pull_request.head.sha }}
      pr_number: ${{ github.event.number }}
      package: datasets # Replace this with your package name
```

Note the use of special arguments like `pr_number` and `package` under the `with` field. You can find the various options by inspecting each of the `doc-builder` [workflow files](https://github.com/huggingface/doc-builder/tree/main/.github/workflows).

### Enabling multilingual documentation

`doc-builder` can also convert documentation that's been translated from the English source into one or more languages. To enable the conversion, the documentation directories should be structured as follows:

```
doc_folder
├── en
│   ├── _toctree.yml
│   ...
└── es
    ├── _toctree.yml
    ...
```

Note that each language directory has it's own table of contents file `_toctree.yml` and that all languages are arranged under a single `doc_folder` directory - see the [`course`](https://github.com/huggingface/course/tree/main/chapters) repo for an example. You can then build the individual language subsets as follows:

```bash
doc-builder {package_name} {path_to_docs} --build_dir {build_dir} --language {lang_id}
```

To automatically build the documentation for all languages via the GitHub Actions templates, simply provide the `languages` argument to your workflow, with a space-separated list of the languages you wish to build, e.g. `languages: en es`.


## Writing documentation for Hugging Face libraries

`doc-builder` expects Markdown so you should write any new documentation in `".mdx"` files for tutorials, guides, API documentations. For docstrings, we follow the [Google format](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html) with the main difference that you should use Markdown instead of restructured text (hopefully, that will be easier!)

Values that should be put in `code` should either be surrounded by backticks: \`like so\`. Note that argument names
and objects like True, None or any strings should usually be put in `code`.

When mentioning a class, function or method, it is recommended to use the following syntax for internal links so that our tool
automarically adds a link to its documentation: \[\`XXXClass\`\] or \[\`function\`\]. This requires the class or 
function to be in the main package.

If you want to create a link to some internal class or function, you need to
provide its path. For instance, in the Transformers documentation \[\`file_utils.ModelOutput\`\] will create a link to the documnetation of `ModelOutput`. This link will have `file_utils.ModelOutput` in the description. To get rid of the path and only keep the name of the object you are
linking to in the description, add a ~: \[\`~file_utils.ModelOutput\`\] will generate a link with `ModelOutput` in the description.

The same works for methods so you can either use \[\`XXXClass.method\`\] or \[~\`XXXClass.method\`\].

Multi-line code blocks can be useful for displaying examples. They are done between two lines of three backticks as usual in Markdown:

````
```
# first line of code
# second line
# etc
```
````

We follow the [doctest](https://docs.python.org/3/library/doctest.html) syntax for the examples to automatically test
the results stay consistent with the library.

To write a block that you'd like to see highlighted as a note or warning, place your content between the following
markers:

```
<Tip>

Write your note here

</Tip>
```

For warnings, change the introduction to `<Tip warning={true}>`.

If your documentation has a block that is framework-dependent (PyTorch vs TensorFlow vs Flax), you can use the
following syntax:

```
<frameworkcontent>
<pt>
PyTorch content goes here
</pt>
<tf>
TensorFlow content goes here
</tf>
<flax>
Flax content goes here
</flax>
</frameworkcontent>
```

Note that all frameworks are optional (you can write a PyTorch-only block for instance) and the order does not matter.


### Writing API documentation

To show the full documentation of any object of the library you are documenting, use the `[[autodoc]]` marker:

```
[[autodoc]] SomeObject
```

If the object is a class, this will include every public method of it that is documented. If for some reason you wish for a method
not to be displayed in the documentation, you can do so by specifying which methods should be in the docs, here is an example:

```
[[autodoc]] XXXTokenizer
    - build_inputs_with_special_tokens
    - get_special_tokens_mask
    - create_token_type_ids_from_sequences
    - save_vocabulary
```

If you just want to add a method that is not documented (for instance magic method like `__call__` are not documented
by default) you can put the list of methods to add in a list that contains `all`:

```
## XXXTokenizer

[[autodoc]] XXXTokenizer
    - all
    - __call__
```

You can create a code-block by referencing a file excerpt with `<literalinclude>` (sphinx-inspired) syntax. 
There should be json between `<literalinclude>` open & close tags.
```
<literalinclude>
{"path": "./data/convert_literalinclude_dummy.txt", # relative path
"language": "python", # defaults to " (empty str)
"start-after": "START python_import",  # defaults to start of file
"end-before": "END python_import",  # defaults to end of file
"dedent": 7 # defaults to 0
}
</literalinclude>
```

### Writing source documentation

Arguments of a function/class/method should be defined with the `Args:` (or `Arguments:` or `Parameters:`) prefix, followed by a line return and
an indentation. The argument should be followed by its type, with its shape if it is a tensor, a colon and its
description:

```
    Args:
        n_layers (`int`): The number of layers of the model.
```

If the description is too long to fit in one line, another indentation is necessary before writing the description
after th argument.

Here's an example showcasing everything so far:

```
    Args:
        input_ids (`torch.LongTensor` of shape `(batch_size, sequence_length)`):
            Indices of input sequence tokens in the vocabulary.

            Indices can be obtained using [`AlbertTokenizer`]. See [`~PreTrainedTokenizer.encode`] and
            [`~PreTrainedTokenizer.__call__`] for details.

            [What are input IDs?](../glossary#input-ids)
```

You can check the full example it comes from [here](https://github.com/huggingface/transformers/blob/v4.17.0/src/transformers/models/bert/modeling_bert.py#L794-L841)

For optional arguments or arguments with defaults we follow the following syntax. Imagine we have a function with the
following signature:

```
def my_function(x: str = None, a: float = 1):
```

then its documentation should look like this:

```
    Args:
        x (`str`, *optional*):
            This argument controls ...
        a (`float`, *optional*, defaults to 1):
            This argument is used to ...
```

Note that we always omit the "defaults to \`None\`" when None is the default for any argument. Also note that even
if the first line describing your argument type and its default gets long, you can't break it on several lines. You can
however write as many lines as you want in the indented description (see the example above with `input_ids`).

If your argument has for type a class defined in the package, you can use the syntax we saw earlier to link to its
documentation:

```
    Args:
         config ([`BertConfig`]):
            Model configuration class with all the parameters of the model.

            Initializing with a config file does not load the weights associated with the model, only the
            configuration. Check out the [`~PreTrainedModel.from_pretrained`] method to load the model weights.
```

The return block should be introduced with the `Returns:` prefix, followed by a line return and an indentation.
The first line should be the type of the return, followed by a line return. No need to indent further for the elements
building the return.

Here's an example for a single value return:

```
    Returns:
        `List[int]`: A list of integers in the range [0, 1] --- 1 for a special token, 0 for a sequence token.
```

Here's an example for tuple return, comprising several objects:

```
    Returns:
        `tuple(torch.FloatTensor)` comprising various elements depending on the configuration ([`BertConfig`]) and inputs:
        - ** loss** (*optional*, returned when `masked_lm_labels` is provided) `torch.FloatTensor` of shape `(1,)` --
          Total loss as the sum of the masked language modeling loss and the next sequence prediction (classification) loss.
        - **prediction_scores** (`torch.FloatTensor` of shape `(batch_size, sequence_length, config.vocab_size)`) --
          Prediction scores of the language modeling head (scores for each vocabulary token before SoftMax).
```
