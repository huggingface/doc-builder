# Copyright 2021 The HuggingFace Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from doc_builder.api_docs import extract_api_docstrings


def test_extracts_top_level_and_nested_docstrings_without_details():
    html = """
    <div class="docstring border-l-2">
      <div>
        <span id="transformers.BertModel">
          <h3>class transformers.BertModel</h3>
          <a href="source.py">source</a>
        </span>
        <p class="font-mono">(config, add_pooling_layer=True)</p>
        <div class="docstring-details">
          <p>Parameters</p>
          <ul><li>config: the model configuration</li></ul>
          <p>Returns</p>
          <p>A tensor.</p>
        </div>
      </div>
      <p>The bare <code>BERT</code> model transformer.</p>
      <p>It can act as an encoder or decoder.</p>
      <div class="docstring border-l-2">
        <div>
          <span id="transformers.BertModel.forward"><h4>forward</h4></span>
          <p class="font-mono">(input_ids)</p>
          <div class="docstring-details"><p>Parameters</p></div>
        </div>
        <p>Runs the model forward pass.</p>
      </div>
    </div>
    """

    assert extract_api_docstrings(html) == [
        (
            "transformers.BertModel",
            "The bare BERT model transformer.\nIt can act as an encoder or decoder.",
        ),
        ("transformers.BertModel.forward", "Runs the model forward pass."),
    ]


def test_truncates_examples_and_keeps_empty_descriptions():
    html = """
    <div class="docstring">
      <div>
        <span id="diffusers.FluxPipeline"><h3>class diffusers.FluxPipeline</h3></span>
        <div class="docstring-details"><p>Parameters</p></div>
      </div>
      <p>The <code>FluxPipeline</code> generates images from text.</p>
      <pre>pipe = FluxPipeline.from_pretrained(...)</pre>
      <p>It supports several model variants.</p>
      <p><strong>Examples:</strong></p>
      <pre>image = pipe("a cat").images[0]</pre>
    </div>
    <div class="docstring docstring-wide">
      <div><span id="diffusers.EmptyModel"><h3>class diffusers.EmptyModel</h3></span></div>
    </div>
    <div class="docstring">
      <div><span id="diffusers.StructuredModel"><h3>class diffusers.StructuredModel</h3></span></div>
      <p>A compact model description.</p>
      <p><strong>Components:</strong></p>
      <ul><li>tokenizer: the tokenizer argument</li></ul>
      <p>Inputs:</p>
      <p>prompt: text to render</p>
    </div>
    <div class="docstring">
      <div><span id="diffusers.CopiedExample"><h3>class diffusers.CopiedExample</h3></span></div>
      <p>A description before generated example code.</p>
      <p>Copied</p>
      <p>Traceback (most recent call last):</p>
    </div>
    <div class="docstring">
      <div><span id="transformers.FlattenedArgs"><h3>transformers.FlattenedArgs</h3></span></div>
      <p>Runs the flattened API.</p>
      <p>last_hidden_state (torch.FloatTensor of shape (batch, length)) — The final hidden state.</p>
      <p>input_ids (torch.Tensor, optional): The input token ids.</p>
      <p>return_dict (bool, optional, defaults to True) — Whether to return a dictionary.</p>
    </div>
    <div class="docstring-details"><div id="not.an.api.object">ignored</div></div>
    """

    assert extract_api_docstrings(html) == [
        (
            "diffusers.FluxPipeline",
            "The FluxPipeline generates images from text.\nIt supports several model variants.",
        ),
        ("diffusers.EmptyModel", ""),
        ("diffusers.StructuredModel", "A compact model description."),
        ("diffusers.CopiedExample", "A description before generated example code."),
        ("transformers.FlattenedArgs", "Runs the flattened API."),
    ]
