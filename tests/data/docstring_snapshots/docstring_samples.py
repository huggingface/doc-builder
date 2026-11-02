"""
Objects whose docstrings cover what the docstring pipeline handles, documented by `docs/page.md` for the docstring
snapshot test (`tests/test_docstring_snapshots.py`). Editing this file changes the snapshots (if only through the
source line numbers): regenerate them as explained in that test.
"""

from dataclasses import dataclass

SPECIAL_TOKENS = {"<s>": 0, "</s>": 1}


class SampleTokenizer:
    r"""
    Construct a sample tokenizer, based on a vocabulary file. Its outputs are described in [`SampleOutput`].

    <Tip>

    Pass `do_lower_case=False` when the vocabulary is cased.

    </Tip>

    Args:
        vocab_file (`str`):
            Path to the vocabulary file.
        do_lower_case (`bool`, *optional*, defaults to `True`):
            Whether or not to lowercase the input when tokenizing.
        > Special tokens
        unk_token (`str`, *optional*, defaults to `"<unk>"`):
            The unknown token. A token that is not in the vocabulary cannot be converted to an ID and is set to be
            this token instead.
        pad_token (`str`, *optional*, defaults to `"<pad>"`):
            The token used for padding, for example when batching sequences of different lengths.

    Example:

    ```python
    >>> from docstring_samples import SampleTokenizer

    >>> tokenizer = SampleTokenizer("vocab.txt")
    >>> tokenizer.encode("Hello world")
    [7592, 2088]
    ```
    """

    def __init__(self, vocab_file, do_lower_case=True, unk_token="<unk>", pad_token="<pad>", **kwargs):
        self.vocab_file = vocab_file

    def encode(self, text: str, max_length: int | None = None, special_tokens: dict[str, int] = SPECIAL_TOKENS):
        """
        Converts a string to a sequence of ids, using the vocabulary.

        Args:
            text (`str`):
                The text to encode. Curly braces like `{"a": 1}` and angle brackets like `<mask>` render as text,
                in code and outside of it: {"a": 1}, a <mask> token, issue #12.
            max_length (`int`, *optional*):
                Maximum length of the returned sequence. When the text is longer:

                - with `truncation=True`, the sequence is cut at `max_length`;
                - otherwise, a warning is logged.

                See [`~SampleTokenizer.decode`] for the reverse operation.
            special_tokens (`dict[str, int]`, *optional*):
                Special tokens to add, mapped to their ids.

        Returns:
            `list[int]`: The token ids, starting with the id of `<s>`.

        Raises:
            ValueError: If `text` is empty.
            `TypeError`: If `text` is not a string, for example when a list of strings is passed instead of a
                single string.
        """

    def decode(self, ids, skip_special_tokens=False):
        """
        Converts a sequence of ids back to a string.

        Args:
            ids (`list[int]`):
                The ids to decode, as returned by [`SampleTokenizer.encode`].
            skip_special_tokens (`bool`, *optional*, defaults to `False`):
                Whether or not to remove the special tokens from the output.

        Returns:
            `str`: The decoded text, without special tokens when
            `skip_special_tokens=True`.
        """

    def iter_batches(self, texts, batch_size=8):
        """
        Encodes texts in batches.

        Args:
            texts (`list[str]`):
                The texts to encode.
            batch_size (`int`, *optional*, defaults to 8):
                The number of texts per batch.

        Yields:
            `list[list[int]]`: The encoded texts, `batch_size` at a time.
        """

    @property
    def vocab_size(self):
        """
        `int`: Size of the vocabulary, special tokens included.
        """
        return 0


@dataclass
class SampleOutput:
    """
    Output of [`sample_function`].

    Args:
        score (`float`):
            The score of the input.
        hidden_states (`tuple(list[float])`, *optional*, returned when `output_hidden_states=True`):
            Hidden states of each layer.

            <Tip warning={true}>

            The first element holds the embeddings, not a layer output.

            </Tip>
    """

    score: float
    hidden_states: tuple | None = None


def sample_function(inputs, *args, threshold: float = 0.5, callback=None, **kwargs):
    """
    Runs the sample pipeline on `inputs`, with the tokenizer [`SampleTokenizer`] and the threshold
    [`sample_function#threshold`].

    Args:
        inputs (`str` or `list[str]`):
            The texts to process.

            A second paragraph makes this a loose list item, where each paragraph is wrapped in its own `<p>`.
        callback (`Callable`, *optional*):
            Called with each [`SampleOutput`].

            <Added version="1.2.0">

            The `callback` argument.

            </Added>
        kwargs (`dict[str, Any]`, *optional*):
            Passed to [`SampleTokenizer.encode`].

            <Deprecated version="2.0.0">

            Use `callback` instead.

            </Deprecated>
        threshold (`float`, *optional*, defaults to 0.5):
            Scores below this value are dropped. The score of a text is computed as:

            ```python
            score = sum(weights) / len(weights)
            ```

            Last in the list: the code block above ends the list, which drops the parameters after it.

    Returns:
        [`SampleOutput`] or `tuple(float)`: A [`SampleOutput`] when `return_dict=True`, otherwise a tuple of
        scores.

    Example:

    ```python
    >>> output = sample_function("Hello")
    >>> output.score
    0.9
    ```
    """


def legacy_function(x, y=2):
    r"""
    Adds :obj:`x` and ``y``, see :class:`~docstring_samples.SampleTokenizer` and :math:`x + y`.

    Args:
        x (:obj:`int`):
            The first number.
        y (:obj:`int`, `optional`, defaults to 2):
            The second number.

    Returns:
        :obj:`int`: The sum.

    Example::

        >>> legacy_function(1)
        3
    """
    return x + y
