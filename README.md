# doc-builder

This is the package we use to build the documentation of our Hugging Face repos.

## Table of Contents

- [doc-builder](#doc-builder)
  * [Installation](#installation)
  * [Previewing](#previewing)
  * [Doc building](#doc-building)
  * [Writing in notebooks](#writing-in-notebooks)
  * [Templates for GitHub Actions](#templates-for-github-actions)
    + [Enabling multilingual documentation](#enabling-multilingual-documentation)
    + [Redirects](#redirects)
  * [Fixing and testing doc-builder](#fixing-and-testing-doc-builder)
  * [Writing documentation for Hugging Face libraries](#writing-documentation-for-hugging-face-libraries)
    + [Internal link to object](#internal-link-to-object)
    + [External link to object](#external-link-to-object)
    + [Tip](#tip)
    + [Framework Content](#framework-content)
    + [Options](#options)
    + [Anchor link](#anchor-link)
    + [LaTeX](#latex)
    + [Code Blocks](#code-blocks)
  * [Writing API documentation (Python)](#writing-api-documentation-python)
    + [Autodoc](#autodoc)
    + [Code Blocks from file references](#code-blocks-from-file-references)
    + [Writing source documentation](#writing-source-documentation)
    + [Description](#description)
    + [Arguments](#arguments)
    + [Attributes](#attributes)
    + [Parmeter typing and default value](#parmeter-typing-and-default-value)
    + [Returns](#returns)
    + [Yields](#yields)
    + [Raises](#raises)
    + [Directives for Added, Changed, Deprecated](#directives-for-added-changed-deprecated)
  * [Developing svelte locally](#developing-svelte-locally)

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

**`preview` command only works with existing doc files. When you add a completely new file, you need to update `_toctree.yml` & restart `preview` command (`ctrl-c` to stop it & call `doc-builder preview ...` again).

**`preview` command does not work with Windows.
## Doc building

To build the documentation of a given package, use the following command:

```bash
#Add --not_python_module if not building doc for a python lib
doc-builder build {package_name} {path_to_docs} --build_dir {build_dir}
```

For instance, here is how you can build the Datasets documentation (requires `pip install datasets[dev]`) if you have cloned the repo in `~/git/datasets`:

```bash
doc-builder build datasets ~/git/datasets/docs/source --build_dir ~/tmp/test-build
```

This will generate MDX files that you can preview like any Markdown file in your favorite editor. To have a look at the documentation in HTML, you need to install node version 14 or higher. Then you can run (still with the example on Datasets)

```bash
doc-builder build datasets ~/git/datasets/docs/source --build_dir ~/tmp/test-build --html
```
which will build HTML files in `~/tmp/test-build`. You can then inspect those files in your browser.

`doc-builder` can also automatically convert some of the documentation guides or tutorials into notebooks. This requires two steps:
- add `[[open-in-colab]]` in the tutorial for which you want to build a notebook
- add `--notebook_dir {path_to_notebook_folder}` to the build command.

## Writing in notebooks

You can write your docs in jupyter notebooks & use doc-builder to: turn jupyter notebooks into mdx files.

In some situations, such as course & tutorials, it makes more sense to write in jupyter notebooks (& use doc-builder converter) rather than writing in mdx files directly.

The process is:
1. In your `build_main_documentation.yml` & `build_pr_documentation.yml` enable the flag [convert_notebooks: true](https://github.com/huggingface/doc-builder/blob/main/.github/workflows/build_main_documentation.yml#L46-L48). 
2. After this flag is enabled, doc-builder will convert all .ipynb files in [path_to_docs](https://github.com/huggingface/doc-builder/blob/main/.github/workflows/build_main_documentation.yml#L19-L20) to mdx files.

Moreover, you can locally convert .ipynb files into mdx files.
```bash
doc-builder notebook-to-mdx {path to notebook file or folder containing notebook files}
```

## Templates for GitHub Actions

`doc-builder` provides templates for GitHub Actions, so you can build your documentation with every pull request, push to some branch etc. To use them in your project, simply create the following three files in the `.github/workflows/` directory:

* `build_main_documentation.yml`: responsible for building the docs for the `main` branch, releases etc.
* `build_pr_documentation.yml`: responsible for building the docs on each PR.
* `upload_pr_documentation.yml`: responsible for uploading the PR artifacts to the Hugging Face Hub.
* `delete_doc_comment_trigger.yml`: responsible for removing the comments from the `HuggingFaceDocBuilder` bot that provides a URL to the PR docs.

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
│   ├── _redirects.yml
│   ...
└── es
    ├── _toctree.yml
    ├── _redirects.yml
    ...
```

Note that each language directory has its own table of contents file `_toctree.yml` and that all languages are arranged under a single `doc_folder` directory - see the [`course`](https://github.com/huggingface/course/tree/main/chapters) repo for an example. You can then build the individual language subsets as follows:

```bash
doc-builder build {package_name} {path_to_docs} --build_dir {build_dir} --language {lang_id}
```

To automatically build the documentation for all languages via the GitHub Actions templates, simply provide the `languages` argument to your workflow, with a space-separated list of the languages you wish to build, e.g. `languages: en es`.

### Redirects

You can optionally provide `_redirects.yml` for "old links". The yml file should look like:

```yml
how_to: getting_started
package_reference/classes: package_reference/main_classes
# old_local: new_local
```

## Fixing and testing doc-builder

If you are working on a fix or an update of the doc-builder tool itself, you will eventually want to test it in the CI of another repository (transformers, diffusers, courses, etc.). To do so you should set the `doc_builder_revision` argument in your workflow file to point to your branch. Here is an example of what it would look like in the [`transformers.js` project](https://github.com/xenova/transformers.js/blob/main/.github/workflows/pr-documentation.yml):

```yml
jobs:
  build:
    uses: huggingface/doc-builder/.github/workflows/build_pr_documentation.yml@my-test-branch
    with:
      repo_owner: xenova
      commit_sha: ${{ github.sha }}
      pr_number: ${{ github.event.number }}
      package: transformers.js
      path_to_docs: transformers.js/docs/source
      pre_command: cd transformers.js && npm install && npm run docs-api
      additional_args: --not_python_module
      doc_builder_revision: my-test-branch # <- add this line
```

Once the docs build is complete in your project, you can drop that change.

## Writing documentation for Hugging Face libraries

`doc-builder` expects Markdown so you should write any new documentation in `".mdx"` files for tutorials, guides, API documentations. For docstrings, we follow the [Google format](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html) with the main difference that you should use Markdown instead of restructured text (hopefully, that will be easier!)

Values that should be put in `code` should either be surrounded by backticks: \`like so\`. Note that argument names
and objects like True, None or any strings should usually be put in `code`.

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

### Internal link to object

Syntax:
```html
[`XXXClass`] or [~`XXXClass`] // for class
[`XXXClass.method`] or [~`XXXClass.method`] // for method
```

Example: [here](https://github.com/huggingface/transformers/blob/eb849f6604c7dcc0e96d68f4851e52e253b9f0e5/docs/source/en/model_doc/sew-d.md?plain=1#L39) & [here](https://github.com/huggingface/transformers/blob/6f79d264422245d88c7a34032c1a8254a0c65752/examples/research_projects/performer/modeling_flax_performer.py#L48) (as used inside docstring).

When mentioning a class, function or method, it is recommended to use the following syntax for internal links so that our tool
automatically adds a link to its documentation: \[\`XXXClass\`\] or \[\`function\`\]. This requires the class or 
function to be in the main package.

If you want to create a link to some internal class or function, you need to
provide its path. For instance, in the Transformers documentation \[\`file_utils.ModelOutput\`\] will create a link to the documentation of `ModelOutput`. This link will have `file_utils.ModelOutput` in the description. To get rid of the path and only keep the name of the object you are
linking to in the description, add a ~: \[\`~file_utils.ModelOutput\`\] will generate a link with `ModelOutput` in the description.

The same works for methods, so you can either use \[\`XXXClass.method\`\] or \[~\`XXXClass.method\`\].

### External link to object

Syntax:
```html
[`XXXLibrary.XXXClass`] or [~`XXXLibrary.XXXClass`] // for class
[`XXXLibrary.XXXClass.method`] or [~`XXXLibrary.XXXClass.method`] // for method
```

Example: [here](https://github.com/huggingface/transformers/blob/0f0e1a2c2bff68541a5b9770d78e0fb6feb7de72/docs/source/en/accelerate.md?plain=1#L29) linking object from `accelerate` inside `transformers`.

### Tip

To write a block that you'd like to see highlighted as a note or warning, place your content between the following
markers.

Syntax:

```md
> [!TIP]
> Here is a tip. Go to this url [website](www.tip.com)
> 
> Second line
```

or

```html
<Tip>

Write your note here

</Tip>
```

Example: [here](https://github.com/huggingface/transformers/blob/0f0e1a2c2bff68541a5b9770d78e0fb6feb7de72/docs/source/en/create_a_model.md#L282-L286)

For warnings, change the introduction to:

Syntax:

```md
> [!WARNING]
```

or

```html
`<Tip warning={true}>`
```

Example: [here](https://github.com/huggingface/transformers/blob/eb849f6604c7dcc0e96d68f4851e52e253b9f0e5/docs/source/de/autoclass_tutorial.md#L102-L108)

### Framework Content

If your documentation has a block that is framework-dependent (PyTorch vs TensorFlow vs Flax), you can use the
following syntax:

Syntax:

```html
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

Example: [here](https://github.com/huggingface/transformers/blob/eb849f6604c7dcc0e96d68f4851e52e253b9f0e5/docs/source/de/autoclass_tutorial.md#L84-L131)

Note: all frameworks are optional (you can write a PyTorch-only block for instance) and the order does not matter.

### Options

Show alternatives (let's say code blocks for different version of a library etc.) in a way where a user can select an option and see the selected option content:

Syntax:

```html
<hfoptions id="some id">
<hfoption id="id for option 1">
{YOUR MARKDOWN}
</hfoption>
<hfoption id="id for option 2">
{YOUR MARKDOWN}
</hfoption>
... however many <hfoption> tags
</hfoptions>
```

Example: [here](https://github.com/huggingface/diffusers/blob/75ea54a1512ac443d517ab35cb9bf45f8d6f326e/docs/source/en/using-diffusers/kandinsky.md?plain=1#L30-L81)

Note: for multiple `<hfoptions id="some id">` in a same page, you may consider using same id so that when a user selects one option it affects all other hfoptions blocks. If you don't want this behaviour, use different ids.

### Anchor link

Anchor links for markdown headings are generated automatically (with the following rule: 1. lowercase, 2. replace space with dash `-`, 3. strip [^a-z0-9-]):

Syntax:
```
## My awesome section
// the anchor link is: `my-awesome-section`
```

Example: [here](https://github.com/huggingface/transformers/blob/eb849f6604c7dcc0e96d68f4851e52e253b9f0e5/docs/source/en/model_doc/bert.md#L132)

Moreover, there is a way to customize the anchor link.

Syntax:
```
## My awesome section[[some-section]]
// the anchor link is: `some-section`
```

Example: [here](https://github.com/huggingface/transformers/blob/eb849f6604c7dcc0e96d68f4851e52e253b9f0e5/docs/source/en/model_summary.md#L79)

### LaTeX

Latex display mode. `$$...$$`

Syntax:

```
$$Y = X * \textbf{dequantize}(W); \text{quantize}(W)$$
```

Example: [here](https://github.com/huggingface/transformers/blob/main/docs/source/en/model_doc/rwkv.md?plain=1#L107)

Latex inline mode. `\\( ... )\\`

Syntax:

```
\\( Y = X * \textbf{dequantize}(W); \text{quantize}(W) )\\
```

Example: [here](https://github.com/huggingface/transformers/blob/main/docs/source/en/model_doc/rwkv.md?plain=1#L93)

### Code Blocks

Code blocks are written using a regular markdown syntax ```. However, there is a special flag you can put in your mdx files to change the wrapping style of the resulting html from overflow/scrollbar to wrap.

Syntax:
```
<!-- WRAP CODE BLOCKS -->
```

Example: [here](https://github.com/huggingface/text-generation-inference/blob/724199aaf172590c3658018c0e6bc6152cda4c2f/docs/source/basic_tutorials/launcher.md?plain=1#L3)

## Writing API documentation (Python)

### Autodoc

To show the full documentation of any object of the python library you are documenting, use the `[[autodoc]]` marker.

Syntax:

```
[[autodoc]] SomeObject
```

Example: [here](https://github.com/huggingface/transformers/blob/eb849f6604c7dcc0e96d68f4851e52e253b9f0e5/docs/source/en/model_doc/bert.md?plain=1#L142)

If the object is a class, this will include every public method of it that is documented. If for some reason you wish for a method
not to be displayed in the documentation, you can do so by specifying which methods should be in the docs, here is an example:

Syntax:

```
[[autodoc]] XXXTokenizer
    - build_inputs_with_special_tokens
    - get_special_tokens_mask
    - create_token_type_ids_from_sequences
    - save_vocabulary
```

Example: [here](https://github.com/huggingface/transformers/blob/eb849f6604c7dcc0e96d68f4851e52e253b9f0e5/docs/source/en/model_doc/bert.md?plain=1#L158-L159)

If you just want to add a method that is not documented (for instance magic method like `__call__` are not documented
by default) you can put the list of methods to add in a list that contains `all`:

Syntax:

```
## XXXTokenizer

[[autodoc]] XXXTokenizer
    - all
    - __call__
```

Example: [here](https://github.com/huggingface/transformers/blob/eb849f6604c7dcc0e96d68f4851e52e253b9f0e5/docs/source/en/model_doc/bert.md?plain=1#L258-L259)

### Code Blocks from file references

You can create a code-block by referencing a file excerpt with `<literalinclude>` (sphinx-inspired) syntax. 
There should be json between `<literalinclude>` open & close tags.

Syntax:

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

### Description

For a class or function description string, use markdown with [all the custom syntax of doc-builder](#writing-documentation-for-hugging-face-libraries).

Example: [here](https://github.com/huggingface/transformers/blob/910faa3e1f1c566b23a0318f78f5caf5bda8d3b2/examples/flax/language-modeling/run_t5_mlm_flax.py#L257-L267)

### Arguments

Arguments of a function/class/method should be defined with the `Args:` (or `Arguments:` or `Parameters:`) prefix, followed by a line return and
an indentation. The argument should be followed by its type, with its shape if it is a tensor, a colon, and its
description:

Syntax:

```
    Args:
        n_layers (`int`): The number of layers of the model.
```

Example: [here](https://github.com/huggingface/transformers/blob/6f79d264422245d88c7a34032c1a8254a0c65752/src/transformers/models/bert/tokenization_bert_fast.py#L168-L198)

If the description is too long to fit in one line, another indentation is necessary before writing the description
after the argument.

Syntax:

```
    Args:
        input_ids (`torch.LongTensor` of shape `(batch_size, sequence_length)`):
            Indices of input sequence tokens in the vocabulary.

            Indices can be obtained using [`AlbertTokenizer`]. See [`~PreTrainedTokenizer.encode`] and
            [`~PreTrainedTokenizer.__call__`] for details.

            [What are input IDs?](../glossary#input-ids)
```

Example: [here](https://github.com/huggingface/transformers/blob/6f79d264422245d88c7a34032c1a8254a0c65752/src/transformers/models/bert/tokenization_bert_fast.py#L173-L175)

You can check the full example it comes from [here](https://github.com/huggingface/transformers/blob/v4.17.0/src/transformers/models/bert/modeling_bert.py#L794-L841)

### Attributes

If a class is similar to that of a dataclass but the parameters do not align to the available attributes of the class, such as in the below example, `Attributes` instance should be rewritten as `**Attributes**` in order to have the documentation properly render these. Otherwise it will assume that `Attributes` is synonymous to `Parameters`.

Syntax:

```diff
  class SomeClass:
      """
      Docstring
-     Attributes:
+     **Attributes**:
          - **attr_a** (`type_a`) -- Doc a
          - **attr_b** (`type_b`) -- Doc b
      """
      def __init__(self, param_a, param_b):
          ...
```

### Parmeter typing and default value

For optional arguments or arguments with defaults we follow the following syntax. Imagine we have a function with the
following signature:

```
def my_function(x: str = None, a: float = 1):
```

then its documentation should look like this:

Syntax: 

```
    Args:
        x (`str`, *optional*):
            This argument controls ...
        a (`float`, *optional*, defaults to 1):
            This argument is used to ...
```

Example: [here](https://github.com/huggingface/transformers/blob/6f79d264422245d88c7a34032c1a8254a0c65752/src/transformers/models/bert/tokenization_bert_fast.py#L176)

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

### Returns

The return block should be introduced with the `Returns:` prefix, followed by a line return and an indentation.
The first line should be the type of the return, followed by a line return. No need to indent further for the elements
building the return.

Here's an example for a single value return:

Syntax:

```
    Returns:
        `List[int]`: A list of integers in the range [0, 1] --- 1 for a special token, 0 for a sequence token.
```

Example: [here](https://github.com/huggingface/transformers/blob/910faa3e1f1c566b23a0318f78f5caf5bda8d3b2/examples/flax/language-modeling/run_t5_mlm_flax.py#L273-L275)

Here's an example for tuple return, comprising several objects:

Syntax:

```
    Returns:
        `tuple(torch.FloatTensor)` comprising various elements depending on the configuration ([`BertConfig`]) and inputs:
        - ** loss** (*optional*, returned when `masked_lm_labels` is provided) `torch.FloatTensor` of shape `(1,)` --
          Total loss as the sum of the masked language modeling loss and the next sequence prediction (classification) loss.
        - **prediction_scores** (`torch.FloatTensor` of shape `(batch_size, sequence_length, config.vocab_size)`) --
          Prediction scores of the language modeling head (scores for each vocabulary token before SoftMax).
```

Example: [here](https://github.com/huggingface/transformers/blob/003a0cf8cc4d78e47ef9debfb1e93a5c1197ca9a/examples/research_projects/bert-loses-patience/pabee/modeling_pabee_albert.py#L107-L130)

### Yields

Similarly, `Yields` is also supported.

Syntax:

```
Yields:
    `tuple[str, io.BufferedReader]`:
        2-tuple (path_within_archive, file_object).
        File object is opened in binary mode.
```

Example: [here](https://github.com/huggingface/datasets/blob/f56fd9d6c877ffa6fb44fb832c13b61227c9cc5b/src/datasets/download/download_manager.py#L459-L462C17)

### Raises

You can also document `Raises`.

Syntax:
```
    Args:
         config ([`BertConfig`]):
            Model configuration class with all the parameters of the model.

            Initializing with a config file does not load the weights associated with the model, only the
            configuration. Check out the [`~PreTrainedModel.from_pretrained`] method to load the model weights.

    Raises:
        `pa.ArrowInvalidError`: if the arrow data casting fails
        TypeError: if the target type is not supported according, e.g.
            - point1
            - point2
        [`HTTPError`](https://2.python-requests.org/en/master/api/#requests.HTTPError) if credentials are invalid
        [`HTTPError`](https://2.python-requests.org/en/master/api/#requests.HTTPError) if connection got lost

    Returns:
        `List[int]`: A list of integers in the range [0, 1] --- 1 for a special token, 0 for a sequence token.
```

Example: [here](https://github.com/huggingface/transformers/blob/1b2381c46b834a89e447f7a01f0961c4e940d117/src/transformers/models/mask2former/image_processing_mask2former.py#L167-L168)

### Directives for Added, Changed, Deprecated

There are directives for `Added`, `Changed`, & `Deprecated`.
Syntax:
```
    Args:
        cache_dir (`str`, *optional*): Directory to cache data.
        config_name (`str`, *optional*): Name of the dataset configuration.
            It affects the data generated on disk: different configurations will have their own subdirectories and
            versions.
            If not provided, the default configuration is used (if it exists).

            <Added version="2.3.0">

            `name` was renamed to `config_name`.

            </Added>
        name (`str`): Configuration name for the dataset.

            <Deprecated version="2.3.0">

            Use `config_name` instead.

            </Deprecated>
```

Example: [here](https://github.com/huggingface/datasets/blob/a1e1867e932f14233244fb25713f3c94c46ff50a/src/datasets/combine.py#L53)

## Developing svelte locally

We use svelte components for doc UI ([Tip component](https://github.com/huggingface/doc-builder/blob/890df105f4173fb8dc299ad6ba3e4db378d2e53d/kit/src/lib/Tip.svelte), [Docstring component](https://github.com/huggingface/doc-builder/blob/a9598feb5a681a3817e58ef8d792349e85a30d1e/kit/src/lib/Docstring.svelte), etc.).

Follow these steps to develop svelte locally:
1. Create this file if it doesn't already exist: `doc-builder/kit/src/routes/_toctree.yml`. Contents should be:
```
- sections: 
  - local: index
    title: Index page
  title: Index page
```
2. Create this file if it doesn't already exist: `doc-builder/kit/src/routes/index.mdx`. Contents should be whatever you'd like to test. For example:
```
<script lang="ts">
import Tip from "$lib/Tip.svelte";
import Youtube from "$lib/Youtube.svelte";
import Docstring from "$lib/Docstring.svelte";
import CodeBlock from "$lib/CodeBlock.svelte";
import CodeBlockFw from "$lib/CodeBlockFw.svelte";
</script>

<Tip>

  [Here](https://myurl.com)

</Tip>

## Some heading
And some text [Here](https://myurl.com)

Physics is the natural science that studies matter,[a] its fundamental constituents, its motion and behavior through space and time, and the related entities of energy and force.[2] Physics is one of the most fundamental scientific disciplines, with its main goal being to understand how the universe behaves.[b][3][4][5] A scientist who specializes in the field of physics is called a physicist.
```
3. Install dependencies & run dev mode
```bash
cd doc-builder/kit
npm ci
npm run dev -- --open
```
4. Start developing. See svelte files in `doc-builder/kit/src/lib` for reference. The flow should be:
    1. Create a svelte component in `doc-builder/kit/src/lib`
    2. Import it & test it in `doc-builder/kit/src/routes/index.mdx`
