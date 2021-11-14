def convert_md_to_mdx(md_text):
    """
    Convert a document written in md to mdx.
    """
    return '''<script>
import Tip from "./Tip.svelte";
import Youtube from "./Youtube.svelte";	
import Docstring from "./Docstring.svelte";	
import CodeBlock from "./CodeBlock.svelte";	
export let fw: "pt" | "tf"
</script>\n'''+md_text
